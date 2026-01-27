import time
import requests
import joblib
import torch
import torch.nn as nn
import numpy as np
from kubernetes import client, config
from prometheus_client import start_http_server, Gauge

# --- PROMETHEUS ---
PPS_GAUGE = Gauge('krrad_traffic_pps', 'Current Packets Per Second')
ATTACK_GAUGE = Gauge('krrad_attack_status', '1=Attack, 0=Safe, 2=Anomaly')
CONFIDENCE_GAUGE = Gauge('krrad_attack_confidence', 'ML Model Confidence')

# --- CONFIG ---
SENSOR_URL = "http://krrad-sensor.kube-system:5000"
RF_PATH = '/app/models/traffic_classifier.pkl'
ISO_PATH = '/app/models/anomaly_detector.pkl' # <--- NEW
RL_PATH = '/app/models/dqn_agent.pth'

# RL Agent Class
class DQN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(DQN, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim, 64), nn.ReLU(),
            nn.Linear(64, 64), nn.ReLU(),
            nn.Linear(64, output_dim)
        )
    def forward(self, x): return self.fc(x)

# Load ALL Brains
print("Loading KRRAD Brains...")
try:
    rf_model = joblib.load(RF_PATH)
    iso_model = joblib.load(ISO_PATH) # <--- Load Isolation Forest
    rl_agent = DQN(4, 3)
    rl_agent.load_state_dict(torch.load(RL_PATH))
    rl_agent.eval()
    print(" - RF, Isolation Forest & RL Agent Loaded.")
except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    exit(1)

def get_traffic_stats():
    try:
        r = requests.get(f"{SENSOR_URL}/metrics", timeout=1)
        return sum(r.json().values())
    except:
        return 0

def execute_mitigation(action):
    if action == 1:
        print(" >> RL Decision: BLOCK IP")
        try: requests.post(f"{SENSOR_URL}/block", json={"ip": "1.2.3.4"}, timeout=1)
        except: pass

# --- MAIN LOOP ---
start_http_server(8000)
print("KRRAD Adaptive Controller Started...")
last_packets = 0

while True:
    time.sleep(1)
    
    curr = get_traffic_stats()
    pps = curr - last_packets
    last_packets = curr
    
    PPS_GAUGE.set(pps)
    print(f"--- Traffic: {pps} PPS ---")
    
    # Feature Vector
    features = [[1.0, pps, 0, pps*60, pps]]
    
    # 1. ASK RANDOM FOREST (The Expert)
    rf_conf = rf_model.predict_proba(features)[0][1]
    CONFIDENCE_GAUGE.set(rf_conf)
    
    # 2. ASK ISOLATION FOREST (The Watchdog)
    # Returns -1 for Anomaly, 1 for Normal
    iso_pred = iso_model.predict(features)[0]
    is_anomaly = (iso_pred == -1)
    
    # --- HYBRID DECISION LOGIC ---
    if rf_conf > 0.5:
        # CASE A: Known Attack (High Confidence)
        print(f"!!! KNOWN ATTACK DETECTED (Conf: {rf_conf:.2f}) !!!")
        ATTACK_GAUGE.set(1)
        
        # RL Mitigation
        norm_pps = min(1.0, pps / 100000.0)
        state = torch.tensor([norm_pps, norm_pps, 0.8, 1.0], dtype=torch.float32)
        action = torch.argmax(rl_agent(state)).item()
        execute_mitigation(action)
        
    elif is_anomaly and rf_conf > 0.3:
        # CASE B: Unknown Anomaly (Zero-Day Potential)
        # RF isn't sure (0.3-0.5), but IsoForest says it's weird.
        print(f"!!! ANOMALY DETECTED (Zero-Day?) - Triggering Defense !!!")
        ATTACK_GAUGE.set(2) # Code 2 for Anomaly
        execute_mitigation(1) # Defensive Block
        
    else:
        # CASE C: Secure
        status = "Abnormal" if is_anomaly else "Normal"
        print(f"Status: Secure ({status}) - Conf: {rf_conf:.2f}")
        ATTACK_GAUGE.set(0)