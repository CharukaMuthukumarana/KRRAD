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
consecutive_blocks = 0

def execute_mitigation(action, pps, target_ip=None):
    global last_action_time, IS_SCALED_UP, consecutive_blocks
    ACTION_GAUGE.set(action)
    
    if action == 0:
        consecutive_blocks = 0
        if IS_SCALED_UP and (datetime.datetime.now() - last_action_time).seconds > COOLDOWN_SECONDS:
            print(f"📉 NORMAL: Restoring baseline scale...")
            try: k8s_apps_v1.patch_namespaced_deployment_scale(name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": 1}})
            except: pass
            IS_SCALED_UP = False
            last_action_time = datetime.datetime.now()
        return "MONITORING"

    if (datetime.datetime.now() - last_action_time).seconds < 5:
        return "COOLDOWN"

    if action == 1:
        # ESCALATION: If blocking internal IP (Proxy) OR repeated failure
        if str(target_ip).startswith('10.244') or consecutive_blocks >= 1:
            print(f"⚠️ ESCALATION: Volumetric Flood detected. Switching to SCALING.")
            action = 2 
        else:
            consecutive_blocks += 1
            print(f"🛡️ RL Decision: BLOCKING (PPS: {pps})")
            if target_ip:
                try: requests.post(f"{SENSOR_URL}/block", json={"ip": target_ip}, timeout=2)
                except: pass
                print(f"[MITIGATION] Action: BLOCKING | PPS: {pps} | Target: {target_ip}")
            last_action_time = datetime.datetime.now()
            return "BLOCKING"
        
    if action == 2:
        print(f"⚖️ RL Decision: SCALING (PPS: {pps})")
        try: k8s_apps_v1.patch_namespaced_deployment_scale(name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": 5}})
        except: pass
        IS_SCALED_UP = True
        consecutive_blocks = 0
        print(f"[MITIGATION] Action: SCALING | PPS: {pps}")
        last_action_time = datetime.datetime.now()
        return "SCALING"
    return "UNKNOWN"

start_http_server(8000)
print("🚀 KRRAD AI Controller Active.")
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
    
    # 2,500 PPS Safety Buffer (Prevents reset blocks)
    if pps < 2500:
        print(f"✅ NORMAL (PPS: {pps})")
        execute_mitigation(0, pps)
        continue

    features_raw = [[pps, 0, pps, 0]]
    features_scaled = scaler.transform(features_raw)
    features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
    with torch.no_grad(): dnn_conf = dnn_model(features_tensor).item()
    
    final_status = 1 if dnn_conf > 0.7 else 0
    state = torch.tensor([[min(1.0, pps / 100000), 0, min(1.0, pps / 50000), 1.0]], dtype=torch.float32)
    with torch.no_grad(): action = torch.argmax(rl_agent(state)).item()

    mitigation = execute_mitigation(max(1, action), pps, target_ip=potential_attacker_ip)
    print(f"🚨 ALERT (PPS: {pps}) | Mitigation: {mitigation}")
