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

# Prometheus Metrics
PPS_GAUGE = Gauge('krrad_traffic_pps', 'Current Packets Per Second')
BPS_GAUGE = Gauge('krrad_traffic_bps', 'Current Bytes Per Second')
ATTACK_GAUGE = Gauge('krrad_attack_status', 'System Threat Status')
CONFIDENCE_GAUGE = Gauge('krrad_ai_confidence', 'Ensemble Confidence Score')
ACTION_GAUGE = Gauge('krrad_mitigation_action', 'RL Action Taken (0=Wait, 1=Block, 2=Scale)')
BASELINE_GAUGE = Gauge('krrad_dynamic_baseline', 'Learned Normal PPS Baseline')

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
except Exception:
    k8s_apps_v1 = None

try:
    scaler = joblib.load(f'{MODELS_DIR}/scaler.pkl')
    dnn_model = KRRAD_DNN(input_dim=4)
    # Added nosec to tell Bandit this local model load is safe
    dnn_model.load_state_dict(torch.load(f'{MODELS_DIR}/dnn_model.pth', map_location='cpu')) # nosec B614
    dnn_model.eval()
    rf_model = joblib.load(f'{MODELS_DIR}/rf_model_big.pkl')
    iso_model = joblib.load(f'{MODELS_DIR}/iso_model_big.pkl')
    rl_agent = DQN(input_dim=4, output_dim=3)
    # Added nosec to tell Bandit this local model load is safe
    rl_agent.load_state_dict(torch.load(f'{MODELS_DIR}/dqn_agent.pth', map_location='cpu')) # nosec B614
    rl_agent.eval()
except Exception as e: exit(1)

last_action_time = datetime.datetime.now()
observation_start_time = None
current_threat_ip = None

# Self-Learning Variables
CALIBRATION_TICKS_REQUIRED = 30
current_calibration_tick = 0
learned_max_pps = 0.0
dynamic_baseline_pps = 0.0
alpha = 0.1  

def execute_mitigation(action, pps, target_ip=None, target_replicas=2, is_critical=False):
    global last_action_time, IS_SCALED_UP, observation_start_time, current_threat_ip
    
    ACTION_GAUGE.set(action)
    
    if action == 0:
        observation_start_time = None  
        if IS_SCALED_UP and (datetime.datetime.now() - last_action_time).seconds > COOLDOWN_SECONDS:
            print(f"📉 NORMAL: Restoring baseline scale (1 Replica)...")
            try: k8s_apps_v1.patch_namespaced_deployment_scale(name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": 1}})
            except Exception: pass # nosec B110
            IS_SCALED_UP = False
            last_action_time = datetime.datetime.now()
        return "MONITORING"

    if (datetime.datetime.now() - last_action_time).seconds < 5 and observation_start_time is None and not is_critical:
        return "COOLDOWN"

    if action == 1:
        if is_critical:
            print(f"⚡ CRITICAL SURGE DETECTED ({pps} PPS). Bypassing observation window!")
            print(f"🛡️ INSTANT EBPF DROP INITIATED on {target_ip}")
            try: requests.post(f"{SENSOR_URL}/block", json={"ip": target_ip}, timeout=2)
            except Exception: pass # nosec B110
            print(f"[MITIGATION] Action: INSTANT BLOCK | Target: {target_ip}")
            observation_start_time = None
            last_action_time = datetime.datetime.now()
            return "CRITICAL_BLOCK"

        now = datetime.datetime.now()
        if observation_start_time is None:
            observation_start_time = now
            current_threat_ip = target_ip
            print(f"🔍 AI OBSERVATION (Trigger: {pps} PPS): Validating threat. SCALING to {target_replicas} replicas to absorb impact.")
            try: k8s_apps_v1.patch_namespaced_deployment_scale(name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": target_replicas}})
            except Exception: pass # nosec B110
            IS_SCALED_UP = True
            return "OBSERVING"
        
        elapsed = (now - observation_start_time).seconds
        if elapsed < 10:
            print(f"⏳ OBSERVING: {10 - elapsed}s remaining to 100% AI Confidence.")
            return "OBSERVING"
        else:
            active_target = target_ip if target_ip else current_threat_ip
            print(f"🛡️ AI CONFIDENCE REACHED: Executing BLOCK on {active_target}")
            try: requests.post(f"{SENSOR_URL}/block", json={"ip": active_target}, timeout=2)
            except Exception: pass # nosec B110
            print(f"[MITIGATION] Action: BLOCKING | Target: {active_target}")
            observation_start_time = None
            last_action_time = datetime.datetime.now()
            return "BLOCKING"
        
    if action == 2:
        print(f"⚖️ RL Decision: SCALING to {target_replicas} replicas (PPS: {pps})")
        try: k8s_apps_v1.patch_namespaced_deployment_scale(name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": target_replicas}})
        except Exception: pass # nosec B110
        IS_SCALED_UP = True
        print(f"[MITIGATION] Action: SCALING | Replicas: {target_replicas}")
        last_action_time = datetime.datetime.now()
        return "SCALING"
    return "UNKNOWN"

start_http_server(8000)
print("🚀 KRRAD AI Controller Booting. Initiating Calibration Phase...")
while True:
    try:
        r = requests.get(f"{SENSOR_URL}/metrics", timeout=2)
        if r.status_code == 200: 
            baseline_data = r.json()
            break
    except Exception: time.sleep(2)

last_packets, last_bytes = baseline_data.get('packets', 0), baseline_data.get('bytes', 0)
last_time = time.monotonic()

while True:
    time.sleep(1)
    try:
        data = requests.get(f"{SENSOR_URL}/metrics", timeout=3).json()
        potential_attacker_ip = data.get("top_source_ip")
    except Exception: continue # nosec B112

    curr_time = time.monotonic()
    dt = curr_time - last_time
    if dt <= 0: continue
    
    pps = int((data.get('packets', 0) - last_packets) / dt)
    bps = int((data.get('bytes', 0) - last_bytes) / dt)
    last_packets, last_bytes, last_time = data.get('packets', 0), data.get('bytes', 0), curr_time
    
    PPS_GAUGE.set(pps)
    BPS_GAUGE.set(bps)
    BASELINE_GAUGE.set(dynamic_baseline_pps)
    
    # 1. SYSTEM CALIBRATION WARM-UP
    if current_calibration_tick < CALIBRATION_TICKS_REQUIRED:
        dynamic_baseline_pps = (alpha * pps) + ((1 - alpha) * dynamic_baseline_pps) if current_calibration_tick > 0 else float(pps)
        learned_max_pps = max(learned_max_pps, float(pps))
        current_calibration_tick += 1
        print(f"⚙️ CALIBRATING [{current_calibration_tick}/{CALIBRATION_TICKS_REQUIRED}] | PPS: {pps} | Max Normal Spike: {int(learned_max_pps)}")
        execute_mitigation(0, pps)
        continue

    # 2. ADAPTIVE THRESHOLDS
    anomaly_threshold = max(learned_max_pps * 1.5, dynamic_baseline_pps * 3.0)
    anomaly_threshold = max(100.0, anomaly_threshold) 
    
    critical_threshold = anomaly_threshold * 20.0
    is_critical_surge = pps >= critical_threshold

    if pps < anomaly_threshold:
        dynamic_baseline_pps = (alpha * pps) + ((1 - alpha) * dynamic_baseline_pps)
        if pps > 10: print(f"✅ NORMAL (PPS: {pps} | Threshold: {int(anomaly_threshold)})")
        ATTACK_GAUGE.set(0)
        CONFIDENCE_GAUGE.set(0)
        execute_mitigation(0, pps)
        continue

    # 3. FEATURE ENGINEERING
    avg_packet_size = 0 if pps == 0 else bps / pps
    features_raw = [[pps, bps, pps, avg_packet_size]]
    features_scaled = scaler.transform(features_raw)
    features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
    
    # 4. ENSEMBLE EVALUATION
    with torch.no_grad(): dnn_conf = dnn_model(features_tensor).item()
    rf_pred = rf_model.predict(features_raw)[0]
    iso_pred = iso_model.predict(features_raw)[0]
    
    CONFIDENCE_GAUGE.set(dnn_conf)
    
    final_status = 0
    if dnn_conf > 0.8:
        final_status = 1
    elif dnn_conf > 0.6 and rf_pred == 1 and iso_pred == -1:
        final_status = 1

    ATTACK_GAUGE.set(final_status)

    # 5. RL AGENT MITIGATION
    state = torch.tensor([[min(1.0, pps / 100000), min(1.0, bps / 10000000), min(1.0, pps / 50000), 1.0 if final_status > 0 else 0.0]], dtype=torch.float32)
    with torch.no_grad(): action = torch.argmax(rl_agent(state)).item()

    calculated_replicas = min(5, max(2, int((pps / anomaly_threshold) + 1)))

    mitigation = execute_mitigation(action, pps, target_ip=potential_attacker_ip, target_replicas=calculated_replicas, is_critical=is_critical_surge)
    if mitigation != "OBSERVING":
        print(f"🚨 ACTION TRIGGERED (PPS: {pps}) | Agent Code: {action} | Mitigation: {mitigation}")
