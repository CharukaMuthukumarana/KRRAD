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
import socket
import struct
from kubernetes import client, config

warnings.filterwarnings("ignore")

# Prometheus Metrics
PPS_GAUGE = Gauge('krrad_traffic_pps', 'Current Packets Per Second')
BPS_GAUGE = Gauge('krrad_traffic_bps', 'Current Bytes Per Second')
ATTACK_GAUGE = Gauge('krrad_attack_status', 'System Threat Status')
CONFIDENCE_GAUGE = Gauge('krrad_ai_confidence', 'Ensemble Confidence Score')
ACTION_GAUGE = Gauge('krrad_mitigation_action', 'RL Action Taken (0=Wait, 1=Block, 2=Scale)')

# Configuration
SENSOR_URL = os.environ.get("SENSOR_URL", "http://krrad-sensor.kube-system:5000")
MODELS_DIR = "/app/models"
SCALING_TARGET = "krrad-target"
NAMESPACE = "default"
COOLDOWN_SECONDS = 5
IS_SCALED_UP = False

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

print("🔌 Connecting to Kubernetes Cluster...")
try:
    config.load_incluster_config()
    k8s_apps_v1 = client.AppsV1Api()
    print("✅ Kubernetes Client Connected.")
except Exception as e:
    print(f"⚠️ Warning: K8s Connection Failed: {e}")
    k8s_apps_v1 = None

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
    print("✅ AI Ensemble loaded successfully.")
except Exception as e:
    print(f"❌ Critical Error Loading Models: {e}")
    exit(1)

last_action_time = datetime.datetime.now()
consecutive_blocks = 0

def get_safe_ips():
    # Added common local IPs
    safe_ips = {"127.0.0.1", "localhost", "0.0.0.0", "192.168.49.1", "10.0.2.2"}
    k8s_host = os.environ.get("KUBERNETES_SERVICE_HOST")
    if k8s_host: safe_ips.add(k8s_host)
    try:
        with open("/proc/net/route") as fh:
            for line in fh:
                fields = line.strip().split()
                if fields[1] == '00000000': 
                    gw_ip = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
                    safe_ips.add(gw_ip)
    except: pass
    return safe_ips

def execute_mitigation(action, pps, target_ip=None):
    global last_action_time, IS_SCALED_UP, consecutive_blocks
    ACTION_GAUGE.set(action)
    
    # 0. MONITORING
    if action == 0:
        consecutive_blocks = 0
        if IS_SCALED_UP and (datetime.datetime.now() - last_action_time).seconds > COOLDOWN_SECONDS:
            print(f"📉 SAFE DETECTED: Scaling down to baseline...")
            if k8s_apps_v1:
                try:
                    k8s_apps_v1.patch_namespaced_deployment_scale(
                        name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": 1}}
                    )
                    IS_SCALED_UP = False
                    print("✅ Scale Down executed.")
                except Exception as e: print(f"❌ Scale Down Failed: {e}")
            last_action_time = datetime.datetime.now()
        return "MONITORING"

    if (datetime.datetime.now() - last_action_time).seconds < COOLDOWN_SECONDS:
        return "COOLDOWN"

    # 1. BLOCKING
    if action == 1:
        if consecutive_blocks >= 2:
            print(f"⚠️ BEHAVIOR ANALYSIS: Repeated blocking failed (Swarm Detected). Escalating to SCALING.")
            action = 2 
        else:
            consecutive_blocks += 1
            if target_ip in get_safe_ips():
                print(f"⚠️ Ignored BLOCK for Safe IP: {target_ip}")
                return "MONITORING"
            
            # --- FIX: Don't block Google Cloud Health Checks or low traffic ---
            if pps < 100:
                print(f"⚠️ Ignoring Low-PPS Alert ({pps} PPS). Likely Health Check.")
                return "MONITORING"

            print(f"🛡️ RL Decision: BLOCKING (PPS: {pps})")
            if target_ip:
                try:
                    requests.post(f"{SENSOR_URL}/block", json={"ip": target_ip}, timeout=2)
                    print(f"⛔ Sent BLOCK command for: {target_ip}")
                except Exception as e: print(f"❌ Block Failed: {e}")
            last_action_time = datetime.datetime.now()
            return "BLOCKING"
        
    # 2. SCALING
    if action == 2:
        print(f"⚖️ RL Decision: SCALING (PPS: {pps})")
        if k8s_apps_v1:
            try:
                k8s_apps_v1.patch_namespaced_deployment_scale(
                    name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": 5}}
                )
                IS_SCALED_UP = True
                consecutive_blocks = 0
                print("✅ Scaling UP command executed.")
            except Exception as e: print(f"❌ Scaling Failed: {e}")
        last_action_time = datetime.datetime.now()
        return "SCALING"

    return "UNKNOWN"

def get_sensor_data_blocking():
    while True:
        try:
            r = requests.get(f"{SENSOR_URL}/metrics", timeout=2)
            if r.status_code == 200: return r.json()
        except: print("⏳ Waiting for Sensor...")
        time.sleep(2)

start_http_server(8000)
print("🚀 KRRAD Controller Live. v4.2-patched (Stuck-Log & GCP-Fix).")
baseline_data = get_sensor_data_blocking()
last_packets = baseline_data.get('packets', 0)
last_bytes = baseline_data.get('bytes', 0)
last_time = time.monotonic()
print("✅ Baseline Established.")

while True:
    time.sleep(1)
    try:
        response = requests.get(f"{SENSOR_URL}/metrics", timeout=1).json()
        data = response
        potential_attacker_ip = response.get("top_source_ip")
    except Exception as e:
        # --- FIX: Print warning instead of staying silent ---
        print(f"⚠️ Sensor Unreachable: {e}")
        continue

    curr_time = time.monotonic()
    curr_packets = data.get('packets', 0)
    curr_bytes = data.get('bytes', 0)
    
    if curr_packets < last_packets:
        print("🔄 Sensor Reset Detected. Recalibrating...")
        last_packets = curr_packets
        last_bytes = curr_bytes
        last_time = curr_time
        continue

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
    
    with torch.no_grad(): dnn_conf = dnn_model(features_tensor).item()
    rf_pred = rf_model.predict(features_raw)[0]
    iso_pred = iso_model.predict(features_raw)[0]
    
    final_status = 0
    if rf_pred == 1 and dnn_conf > 0.8: final_status = 1
    elif dnn_conf > 0.95: final_status = 1
    elif iso_pred == -1 and pps > 100: final_status = 2
    
    # RL Agent
    norm_pps = min(1.0, pps / 100000)
    norm_bps = min(1.0, bps / 10000000)
    est_cpu = min(1.0, pps / 50000)
    norm_attack = 1.0 if final_status > 0 else 0.0
    
    state = torch.tensor([[norm_pps, norm_bps, est_cpu, norm_attack]], dtype=torch.float32)
    with torch.no_grad():
        action = torch.argmax(rl_agent(state)).item()

    # --- FIX: Ensure Safety Net is Respected ---
    if pps < 100: 
        action = 0
    elif final_status >= 1 and action == 0: 
        action = 1

    mitigation = execute_mitigation(action, pps, target_ip=potential_attacker_ip)

    status_text = {0: "SAFE", 1: "ATTACK", 2: "SUSPICIOUS"}.get(final_status, "UNKNOWN")
    if final_status > 0:
        print(f"🚨 {status_text} (PPS: {pps}) | Action: {mitigation}")
    else:
        print(f"✅ {status_text} (PPS: {pps}) | Action: MONITORING")
        
    PPS_GAUGE.set(pps)
    BPS_GAUGE.set(bps)
    ATTACK_GAUGE.set(final_status)
    CONFIDENCE_GAUGE.set(dnn_conf)
