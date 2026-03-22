import time
import requests
import joblib
import torch
import torch.nn as nn
import numpy as np
import datetime
from prometheus_client import start_http_server, Gauge
import warnings
import os
from kubernetes import client, config

warnings.filterwarnings("ignore")

PPS_GAUGE = Gauge('krrad_traffic_pps', 'Current Packets Per Second')
BPS_GAUGE = Gauge('krrad_traffic_bps', 'Current Bytes Per Second')
ATTACK_GAUGE = Gauge('krrad_attack_status', 'System Threat Status')
CONFIDENCE_GAUGE = Gauge('krrad_ai_confidence', 'Ensemble Confidence Score')
ACTION_GAUGE = Gauge('krrad_mitigation_action', 'RL Action Taken (0=Wait, 1=Block, 2=Scale)')

SENSOR_URL = os.environ.get("SENSOR_URL", "http://krrad-sensor.kube-system:5000")
MODELS_DIR = "/app/models"
SCALING_TARGET = "krrad-target"
NAMESPACE = "default"
COOLDOWN_SECONDS = 10
IS_SCALED_UP = False

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
        self.fc = nn.Sequential(nn.Linear(input_dim, 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, output_dim))
    def forward(self, x):
        return self.fc(x)

try:
    config.load_incluster_config()
    k8s_apps_v1 = client.AppsV1Api()
except:
    k8s_apps_v1 = None

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
except Exception as e: exit(1)

last_action_time = datetime.datetime.now()
observation_start_time = None
current_threat_ip = None

def execute_mitigation(action, pps, target_ip=None):
    global last_action_time, IS_SCALED_UP, observation_start_time, current_threat_ip
    ACTION_GAUGE.set(action)
    
    if action == 0:
        observation_start_time = None  
        if IS_SCALED_UP and (datetime.datetime.now() - last_action_time).seconds > COOLDOWN_SECONDS:
            print(f"📉 NORMAL: Restoring baseline scale (1 Replica)...")
            try: k8s_apps_v1.patch_namespaced_deployment_scale(name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": 1}})
            except: pass
            IS_SCALED_UP = False
            last_action_time = datetime.datetime.now()
        return "MONITORING"

    if (datetime.datetime.now() - last_action_time).seconds < 5 and observation_start_time is None:
        return "COOLDOWN"

    if action == 1:
        now = datetime.datetime.now()
        if observation_start_time is None or current_threat_ip != target_ip:
            observation_start_time = now
            current_threat_ip = target_ip
            print(f"🔍 AI OBSERVATION: Validating threat from {target_ip}. SCALING UP to absorb impact.")
            try: k8s_apps_v1.patch_namespaced_deployment_scale(name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": 5}})
            except: pass
            IS_SCALED_UP = True
            return "OBSERVING"
        
        elapsed = (now - observation_start_time).seconds
        if elapsed < 10:
            print(f"⏳ OBSERVING: {10 - elapsed}s remaining to 100% AI Confidence.")
            return "OBSERVING"
        else:
            print(f"🛡️ AI CONFIDENCE REACHED: Executing BLOCK on {target_ip}")
            try: requests.post(f"{SENSOR_URL}/block", json={"ip": target_ip}, timeout=2)
            except: pass
            print(f"[MITIGATION] Action: BLOCKING | PPS: {pps} | Target: {target_ip}")
            observation_start_time = None
            last_action_time = datetime.datetime.now()
            return "BLOCKING"
        
    if action == 2:
        print(f"⚖️ RL Decision: SCALING (PPS: {pps})")
        try: k8s_apps_v1.patch_namespaced_deployment_scale(name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": 5}})
        except: pass
        IS_SCALED_UP = True
        print(f"[MITIGATION] Action: SCALING | PPS: {pps}")
        last_action_time = datetime.datetime.now()
        return "SCALING"
    return "UNKNOWN"

start_http_server(8000)
print("🚀 KRRAD AI Controller Active. Full ML Ensemble Enabled.")
while True:
    try:
        r = requests.get(f"{SENSOR_URL}/metrics", timeout=2)
        if r.status_code == 200: 
            baseline_data = r.json()
            break
    except: time.sleep(2)

last_packets, last_bytes = baseline_data.get('packets', 0), baseline_data.get('bytes', 0)
last_time = time.monotonic()

while True:
    time.sleep(1)
    try:
        data = requests.get(f"{SENSOR_URL}/metrics", timeout=3).json()
        potential_attacker_ip = data.get("top_source_ip")
    except: continue

    curr_time = time.monotonic()
    pps = int((data.get('packets', 0) - last_packets) / (curr_time - last_time)) if (curr_time - last_time) > 0 else 0
    last_packets, last_bytes, last_time = data.get('packets', 0), data.get('bytes', 0), curr_time
    
    if pps < 1500:
        if pps > 10: print(f"✅ NORMAL (PPS: {pps})")
        execute_mitigation(0, pps)
        continue

    # 1. Feature Engineering
    features_raw = [[pps, 0, pps, 0]]
    features_scaled = scaler.transform(features_raw)
    features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
    
    # 2. AI Ensemble Voting System
    # A) Deep Neural Network Prediction
    with torch.no_grad(): dnn_conf = dnn_model(features_tensor).item()
    
    # B) Random Forest Prediction (1 = Attack, 0 = Normal)
    rf_pred = rf_model.predict(features_raw)[0]
    
    # C) Isolation Forest Prediction (-1 = Anomaly/Attack, 1 = Normal)
    iso_pred = iso_model.predict(features_raw)[0]
    
    # Decision Logic: If DNN is highly confident (>80%), OR if DNN is moderately confident (>60%) AND both RF & ISO agree it's an anomaly.
    final_status = 0
    if dnn_conf > 0.8:
        final_status = 1
    elif dnn_conf > 0.6 and rf_pred == 1 and iso_pred == -1:
        final_status = 1

    # 3. RL Agent State mapping
    state = torch.tensor([[min(1.0, pps / 100000), 0, min(1.0, pps / 50000), 1.0 if final_status > 0 else 0.0]], dtype=torch.float32)
    with torch.no_grad(): action = torch.argmax(rl_agent(state)).item()

    mitigation = execute_mitigation(max(1, action), pps, target_ip=potential_attacker_ip)
    if mitigation != "OBSERVING":
        print(f"🚨 ALERT (PPS: {pps}) | Mitigation: {mitigation}")
