import time
import requests
import joblib
import torch
import torch.nn as nn
import numpy as np
import subprocess
import datetime
from prometheus_client import start_http_server, Gauge
import warnings
import os

# Silence warnings
warnings.filterwarnings("ignore")

# --- PROMETHEUS METRICS ---
PPS_GAUGE = Gauge('krrad_traffic_pps', 'Current Packets Per Second')
BPS_GAUGE = Gauge('krrad_traffic_bps', 'Current Bytes Per Second')
ATTACK_GAUGE = Gauge('krrad_attack_status', 'System Threat Status')
CONFIDENCE_GAUGE = Gauge('krrad_ai_confidence', 'Ensemble Confidence Score')
ACTION_GAUGE = Gauge('krrad_mitigation_action', 'RL Action Taken (0=Wait, 1=Block, 2=Scale)')

# --- CONFIG ---
SENSOR_URL = "http://krrad-sensor.kube-system:5000"
MODELS_DIR = "/app/models"
SCALING_TARGET = "deployment/krrad-sensor"
NAMESPACE = "kube-system"

# --- MODEL DEFINITIONS ---
class KRRAD_DNN(nn.Module):
    def __init__(self, input_dim):
        super(KRRAD_DNN, self).__init__()
        self.layer1 = nn.Sequential(nn.Linear(input_dim, 128), nn.BatchNorm1d(128), nn.LeakyReLU(0.1), nn.Dropout(0.2))
        self.layer2 = nn.Sequential(nn.Linear(128, 64), nn.BatchNorm1d(64), nn.LeakyReLU(0.1), nn.Dropout(0.2))
        self.layer3 = nn.Sequential(nn.Linear(64, 32), nn.BatchNorm1d(32), nn.LeakyReLU(0.1))
        self.output = nn.Linear(32, 1)
        self.sigmoid = nn.Sigmoid()
    def forward(self, x):
        return self.sigmoid(self.output(self.layer3(self.layer2(self.layer1(x)))))

class DQN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(DQN, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim)
        )
    def forward(self, x):
        return self.fc(x)

# --- LOAD BRAINS ---
print("🧠 Initializing KRRAD AI Core...")
try:
    scaler = joblib.load(f'{MODELS_DIR}/scaler.pkl')
    dnn_model = KRRAD_DNN(input_dim=4)
    dnn_model.load_state_dict(torch.load(f'{MODELS_DIR}/lstm_model.pth', map_location='cpu'))
    dnn_model.eval()
    rf_model = joblib.load(f'{MODELS_DIR}/rf_model_big.pkl')
    iso_model = joblib.load(f'{MODELS_DIR}/iso_model_big.pkl')
    
    rl_agent = DQN(input_dim=4, output_dim=3)
    rl_agent.load_state_dict(torch.load(f'{MODELS_DIR}/dqn_agent.pth', map_location='cpu'))
    rl_agent.eval()
    print("✅ ENSEMBLE + RL AGENT LOADED SUCCESSFULLY.")
except Exception as e:
    print(f"❌ CRITICAL LOAD ERROR: {e}")
    exit(1)

# --- MITIGATION LOGIC ---
last_action_time = datetime.datetime.now()
COOLDOWN_SECONDS = 30

def execute_mitigation(action, pps):
    global last_action_time
    ACTION_GAUGE.set(action)
    
    if action == 0: return "MONITORING"
    if (datetime.datetime.now() - last_action_time).seconds < COOLDOWN_SECONDS:
        return "COOLDOWN"
        
    if action == 1:
        print(f"🛡️ RL DECISION: BLOCK ATTACK SIGNATURE (PPS: {pps})")
        last_action_time = datetime.datetime.now()
        return "BLOCKING"
        
    elif action == 2:
        print(f"⚖️ RL DECISION: SCALING RESOURCES (PPS: {pps})")
        try:
            subprocess.run(["kubectl", "scale", SCALING_TARGET, "--replicas=5", "-n", NAMESPACE], check=False)
        except: pass
        last_action_time = datetime.datetime.now()
        return "SCALING"

# --- HELPER: ROBUST POLLING ---
def get_sensor_data_blocking():
    """Blocks until valid data is received from Sensor. Used for initialization."""
    while True:
        try:
            r = requests.get(f"{SENSOR_URL}/metrics", timeout=2)
            if r.status_code == 200:
                return r.json()
        except:
            print("⏳ Waiting for Sensor connection...")
        time.sleep(2)

# --- MAIN EXECUTION ---
start_http_server(8000)
print("🚀 KRRAD Controller Live: Establishing Baseline...")

# 1. INITIALIZATION PHASE (Outside the Loop)
# We fetch the *first* reading here to set the baseline.
# This prevents the "Startup Spike" without needing a boolean flag inside the loop.
baseline_data = get_sensor_data_blocking()

last_packets = baseline_data.get('packets', 0)
last_bytes = baseline_data.get('bytes', 0)
last_time = time.monotonic() # High-precision clock

print("✅ Baseline Established. Monitoring Active.")

# 2. MONITORING LOOP
while True:
    # We still sleep to pace the polling, but it doesn't dictate the math.
    time.sleep(1)
    
    # Fetch current state
    try:
        data = requests.get(f"{SENSOR_URL}/metrics", timeout=1).json()
    except:
        continue # Skip this tick if sensor momentarily fails

    curr_time = time.monotonic()
    curr_packets = data.get('packets', 0)
    curr_bytes = data.get('bytes', 0)
    
    # 3. Delta Calculation (The Correct Way)
    # We use actual time difference (dt) to calculate rates
    dt = curr_time - last_time
    if dt <= 0: continue # Prevent division by zero
    
    # Rate = Delta / Time_Delta
    pps = int((curr_packets - last_packets) / dt)
    bps = int((curr_bytes - last_bytes) / dt)
    
    # Update baseline for next loop
    last_packets = curr_packets
    last_bytes = curr_bytes
    last_time = curr_time
    
    # --- AI INFERENCE (Same as before) ---
    avg_packet_size = 0 if pps == 0 else bps / pps
    features_raw = [[pps, bps, pps, avg_packet_size]]
    features_scaled = scaler.transform(features_raw)
    features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
    
    with torch.no_grad():
        dnn_conf = dnn_model(features_tensor).item()
    rf_pred = rf_model.predict(features_raw)[0]
    iso_pred = iso_model.predict(features_raw)[0]
    
    final_status = 0
    if rf_pred == 1 and dnn_conf > 0.8: final_status = 1
    elif dnn_conf > 0.95: final_status = 1
    elif iso_pred == -1 and pps > 100: final_status = 2
    
    # --- RL AGENT ---
    norm_pps = min(1.0, pps / 100000)
    norm_bps = min(1.0, bps / 10000000)
    est_cpu = min(1.0, pps / 50000)
    norm_attack = 1.0 if final_status > 0 else 0.0
    
    state = torch.tensor([[norm_pps, norm_bps, est_cpu, norm_attack]], dtype=torch.float32)
    with torch.no_grad():
        action = torch.argmax(rl_agent(state)).item()
    
    if final_status == 1 and action == 0: action = 1 # Safety override
    mitigation = execute_mitigation(action, pps)

    # --- LOGGING ---
    status_map = {0: "SAFE", 1: "ATTACK", 2: "SUSPICIOUS"}
    status_text = status_map.get(final_status, "UNKNOWN")
    
    if final_status > 0:
        print(f"🚨 {status_text} (PPS: {pps}) | Action: {mitigation}")
    else:
        # Heartbeat log
        print(f"✅ {status_text} (PPS: {pps}) | Action: MONITORING")
        
    PPS_GAUGE.set(pps)
    BPS_GAUGE.set(bps)
    ATTACK_GAUGE.set(final_status)
    CONFIDENCE_GAUGE.set(dnn_conf)