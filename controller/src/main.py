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

warnings.filterwarnings("ignore")

# Prometheus Metrics
PPS_GAUGE = Gauge('krrad_traffic_pps', 'Current Packets Per Second')
BPS_GAUGE = Gauge('krrad_traffic_bps', 'Current Bytes Per Second')
ATTACK_GAUGE = Gauge('krrad_attack_status', 'System Threat Status')
CONFIDENCE_GAUGE = Gauge('krrad_ai_confidence', 'Ensemble Confidence Score')
ACTION_GAUGE = Gauge('krrad_mitigation_action', 'RL Action Taken (0=Wait, 1=Block, 2=Scale)')

# Configuration
SENSOR_URL = "http://krrad-sensor.kube-system:5000"
MODELS_DIR = "/app/models"
SCALING_TARGET = "deployment/krrad-sensor"
NAMESPACE = "kube-system"
COOLDOWN_SECONDS = 30

# Deep Learning Model
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

# RL Agent
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

# Initialize AI Core
print("Initializing KRRAD AI Core...")
try:
    scaler = joblib.load(f'{MODELS_DIR}/scaler.pkl')
    
    dnn_model = KRRAD_DNN(input_dim=4)
    dnn_model.load_state_dict(torch.load(f'{MODELS_DIR}/dnn_model.pth', map_location='cpu'))
    dnn_model.eval()
    
    rf_model = joblib.load(f'{MODELS_DIR}/rf_model_big.pkl')
    iso_model = joblib.load(f'{MODELS_DIR}/iso_model_big.pkl')
    
    rl_agent = DQN(input_dim=4, output_dim=3)
    rl_agent.load_state_dict(torch.load(f'{MODELS_DIR}/dqn_agent.pth', map_location='cpu'))
    rl_agent.eval()
    
    print("✅ AI Ensemble and RL Agent loaded successfully.")
except Exception as e:
    print(f"❌ Critical Error Loading Models: {e}")
    exit(1)

# Mitigation Logic
last_action_time = datetime.datetime.now()

def execute_mitigation(action, pps):
    global last_action_time
    ACTION_GAUGE.set(action)
    
    if action == 0:
        return "MONITORING"
        
    if (datetime.datetime.now() - last_action_time).seconds < COOLDOWN_SECONDS:
        return "COOLDOWN"
        
    if action == 1:
        print(f"🛡️ RL Decision: Block Attack Signature (PPS: {pps})")
        last_action_time = datetime.datetime.now()
        return "BLOCKING"
        
    elif action == 2:
        print(f"⚖️ RL Decision: Scaling Resources (PPS: {pps})")
        try:
            subprocess.run(["kubectl", "scale", SCALING_TARGET, "--replicas=5", "-n", NAMESPACE], check=False)
        except Exception as e:
            print(f"Scaling Error: {e}")
        last_action_time = datetime.datetime.now()
        return "SCALING"

def get_sensor_data_blocking():
    while True:
        try:
            r = requests.get(f"{SENSOR_URL}/metrics", timeout=2)
            if r.status_code == 200:
                return r.json()
        except:
            print("⏳ Waiting for Sensor connection...")
        time.sleep(2)

# Main Execution Loop
start_http_server(8000)
print("🚀 KRRAD Controller Live. Establishing Baseline...")

# Initialize Baseline
baseline_data = get_sensor_data_blocking()
last_packets = baseline_data.get('packets', 0)
last_bytes = baseline_data.get('bytes', 0)
last_time = time.monotonic()

print("✅ Baseline Established. Monitoring Active.")

while True:
    time.sleep(1)
    
    try:
        data = requests.get(f"{SENSOR_URL}/metrics", timeout=1).json()
    except:
        continue

    curr_time = time.monotonic()
    curr_packets = data.get('packets', 0)
    curr_bytes = data.get('bytes', 0)
    
    # Calculate Deltas
    dt = curr_time - last_time
    if dt <= 0: continue
    
    pps = int((curr_packets - last_packets) / dt)
    bps = int((curr_bytes - last_bytes) / dt)
    
    last_packets = curr_packets
    last_bytes = curr_bytes
    last_time = curr_time
    
    # AI Inference
    avg_packet_size = 0 if pps == 0 else bps / pps
    features_raw = [[pps, bps, pps, avg_packet_size]]
    features_scaled = scaler.transform(features_raw)
    features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
    
    with torch.no_grad():
        dnn_conf = dnn_model(features_tensor).item()
    rf_pred = rf_model.predict(features_raw)[0]
    iso_pred = iso_model.predict(features_raw)[0]
    
    # Consensus Engine
    final_status = 0
    if rf_pred == 1 and dnn_conf > 0.8:
        final_status = 1
    elif dnn_conf > 0.95:
        final_status = 1
    elif iso_pred == -1 and pps > 100:
        final_status = 2
    
    # Reinforcement Learning Step
    norm_pps = min(1.0, pps / 100000)
    norm_bps = min(1.0, bps / 10000000)
    est_cpu = min(1.0, pps / 50000)
    norm_attack = 1.0 if final_status > 0 else 0.0
    
    state = torch.tensor([[norm_pps, norm_bps, est_cpu, norm_attack]], dtype=torch.float32)
    with torch.no_grad():
        action = torch.argmax(rl_agent(state)).item()

    if pps < 100:
        action = 0
    
    # Safety Override
    if final_status >= 1 and action == 0:
        action = 1
    
    mitigation = execute_mitigation(action, pps)

    # Logging
    status_text = {0: "SAFE", 1: "ATTACK", 2: "SUSPICIOUS"}.get(final_status, "UNKNOWN")
    
    if final_status > 0:
        print(f"🚨 {status_text} (PPS: {pps}) | Action: {mitigation}")
    else:
        print(f"✅ {status_text} (PPS: {pps}) | Action: MONITORING")
        
    PPS_GAUGE.set(pps)
    BPS_GAUGE.set(bps)
    ATTACK_GAUGE.set(final_status)
    CONFIDENCE_GAUGE.set(dnn_conf)