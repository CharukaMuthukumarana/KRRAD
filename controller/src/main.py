import time
import requests
import joblib
import torch
import torch.nn as nn
import numpy as np
import datetime
from datetime import timezone
from prometheus_client import start_http_server, Gauge
import warnings
import os
from kubernetes import client, config

warnings.filterwarnings("ignore")

# Prometheus metrics
PPS_GAUGE = Gauge('krrad_traffic_pps', 'Current Packets Per Second')
BPS_GAUGE = Gauge('krrad_traffic_bps', 'Current Bytes Per Second')
ATTACK_GAUGE = Gauge('krrad_attack_status', 'System Threat Status')
CONFIDENCE_GAUGE = Gauge('krrad_ai_confidence', 'Ensemble Confidence Score')
ACTION_GAUGE = Gauge('krrad_mitigation_action', 'RL Action Taken (0=Wait, 1=Block, 2=Scale)')
BASELINE_GAUGE = Gauge('krrad_dynamic_baseline', 'Learned Normal PPS Baseline')

# Configuration
SENSOR_URL = os.environ.get("SENSOR_URL", "http://krrad-sensor.kube-system:5000")
MODELS_DIR = "/app/models"
SCALING_TARGET = "krrad-target"
NAMESPACE = "default"
COOLDOWN_SECONDS = 10
MAX_REPLICAS = 5
IS_SCALED_UP = False
consecutive_blocks = 0


class KRRAD_DNN(nn.Module):
    def __init__(self, input_dim):
        super(KRRAD_DNN, self).__init__()
        self.layer1 = nn.Sequential(nn.Linear(input_dim, 16), nn.BatchNorm1d(16), nn.LeakyReLU(0.1), nn.Dropout(0.3))
        self.layer2 = nn.Sequential(nn.Linear(16, 8), nn.BatchNorm1d(8), nn.LeakyReLU(0.1), nn.Dropout(0.3))
        self.output = nn.Linear(8, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        return self.sigmoid(self.output(self.layer2(self.layer1(x))))


class DQN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(DQN, self).__init__()
        self.fc = nn.Sequential(nn.Linear(input_dim, 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, output_dim))

    def forward(self, x):
        return self.fc(x)


# Load Kubernetes client
try:
    config.load_incluster_config()
    k8s_apps_v1 = client.AppsV1Api()
except (config.ConfigException, Exception):  # nosec broad-except
    k8s_apps_v1 = None

# Load ML models
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
except (OSError, RuntimeError, Exception) as e:  # nosec broad-except
    print(f"Failed to load models: {e}")
    exit(1)

# Runtime state
last_action_time = datetime.datetime.now(timezone.utc)
observation_start_time = None
current_threat_ip = None

# Self-learning variables
CALIBRATION_TICKS_REQUIRED = 30
current_calibration_tick = 0
learned_max_pps = 0.0
learned_max_bps = 0.0
dynamic_baseline_pps = 0.0
alpha = 0.1


def get_safe_ips():
    return ["127.0.0.1", "localhost", "10.96.0.1"]


def get_sensor_data_blocking():
    print("Waiting for eBPF sensor metrics...", flush=True)
    while True:
        try:
            r = requests.get(f"{SENSOR_URL}/metrics", timeout=2)
            if r.status_code == 200:
                return r.json()
        except Exception:  # nosec broad-except
            time.sleep(2)

def calculate_queueing_cpu(pps, k8s_apps_v1, learned_pod_capacity):
    learned_pod_capacity = max(learned_pod_capacity, 10.0) 
    
    if not k8s_apps_v1:
        return min(1.0, pps / learned_pod_capacity)
        
    try:
        deployment = k8s_apps_v1.read_namespaced_deployment(name=SCALING_TARGET, namespace=NAMESPACE)
        replicas = deployment.spec.replicas or 1

        total_cluster_capacity = replicas * learned_pod_capacity
        
        return min(1.0, pps / total_cluster_capacity)
    except Exception:
        return min(1.0, pps / learned_pod_capacity)


def execute_mitigation(action, pps, target_ip=None, target_replicas_delta=2, is_critical=False, is_safe=False):
    global last_action_time, IS_SCALED_UP, observation_start_time, current_threat_ip, consecutive_blocks

    ACTION_GAUGE.set(action)
    now = datetime.datetime.now(timezone.utc)
    time_since_last = (now - last_action_time).seconds

    if is_safe:
        consecutive_blocks = 0
        observation_start_time = None
        if IS_SCALED_UP and time_since_last > COOLDOWN_SECONDS:
            print("SAFE DETECTED: Scaling down to baseline...", flush=True)
            if k8s_apps_v1:
                try:
                    k8s_apps_v1.patch_namespaced_deployment_scale(
                        name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": 1}}
                    )
                    IS_SCALED_UP = False
                except (Exception,) as e:  # nosec broad-except
                    print(f"Scale Down Failed: {e}")
            last_action_time = now
        return "MONITORING"

    if observation_start_time is not None:
        elapsed = (now - observation_start_time).seconds
        if elapsed >= 10:
            action = 1  

    # 1. BLOCKING
    if action == 1 or is_critical:
        if target_ip in get_safe_ips():
            return "MONITORING"

        # Instant block for critical surges
        if is_critical:
            print("CRITICAL SURGE DETECTED! Bypassing Observation Window for INSTANT BLOCK.", flush=True)
            active_target = target_ip if target_ip else current_threat_ip
            if active_target:
                try:
                    requests.post(f"{SENSOR_URL}/block", json={"ip": active_target}, timeout=2)
                except (requests.exceptions.RequestException, Exception) as e:  # nosec broad-except
                    pass
            observation_start_time = None
            last_action_time = now
            return "INSTANT BLOCKING"

        # Start observation window on first trigger AND proactively scale up
        if observation_start_time is None:
            observation_start_time = now
            current_threat_ip = target_ip
            print(f"AI OBSERVATION (Trigger: {pps} PPS): Validating threat. Proactively SCALING to absorb impact...", flush=True)
            if k8s_apps_v1:
                try:
                    deployment = k8s_apps_v1.read_namespaced_deployment(name=SCALING_TARGET, namespace=NAMESPACE)
                    current_replicas = deployment.spec.replicas or 1
                    new_replicas = min(MAX_REPLICAS, current_replicas + target_replicas_delta)
                    
                    k8s_apps_v1.patch_namespaced_deployment_scale(
                        name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": new_replicas}}
                    )
                    IS_SCALED_UP = True
                except (Exception,) as e:  # nosec broad-except
                    pass
            return "OBSERVING"

        elapsed = (now - observation_start_time).seconds
        if elapsed < 10:
            print(f"OBSERVING: {10 - elapsed}s remaining to AI Confidence.", flush=True)
            return "OBSERVING"
        else:
            active_target = target_ip if target_ip else current_threat_ip
            if active_target:
                try:
                    requests.post(f"{SENSOR_URL}/block", json={"ip": active_target}, timeout=2)
                except (requests.exceptions.RequestException, Exception) as e:  # nosec broad-except
                    pass
            observation_start_time = None
            last_action_time = now
            return "BLOCKING"

    # 2. SCALING
    if action == 2:
        if time_since_last < COOLDOWN_SECONDS:
            return "COOLDOWN"
        if k8s_apps_v1:
            try:
                deployment = k8s_apps_v1.read_namespaced_deployment(name=SCALING_TARGET, namespace=NAMESPACE)
                current_replicas = deployment.spec.replicas or 1
                new_replicas = min(MAX_REPLICAS, current_replicas + target_replicas_delta)
                
                k8s_apps_v1.patch_namespaced_deployment_scale(
                    name=SCALING_TARGET, namespace=NAMESPACE, body={"spec": {"replicas": new_replicas}}
                )
                IS_SCALED_UP = True
            except (Exception,) as e:  # nosec broad-except
                pass
        last_action_time = now
        return "SCALING"

    return "MONITORING"


# Start Prometheus metrics server and wait for sensor
start_http_server(8000)
print("KRRAD Controller is Live.", flush=True)
baseline_data = get_sensor_data_blocking()
last_packets = baseline_data.get('packets', 0)
last_bytes = baseline_data.get('bytes', 0)
last_time = time.monotonic()

# Main control loop
while True:
    time.sleep(1)
    try:
        data = requests.get(f"{SENSOR_URL}/metrics", timeout=3).json()
        potential_attacker_ip = data.get("top_source_ip")
        ip_entropy = data.get("ip_entropy", 0.0)
    except Exception: continue # nosec B112

    curr_time = time.monotonic()
    dt = curr_time - last_time
    if dt <= 0:
        continue

    pps = int((data.get('packets', 0) - last_packets) / dt)
    bps = int((data.get('bytes', 0) - last_bytes) / dt)
    last_packets, last_bytes, last_time = data.get('packets', 0), data.get('bytes', 0), curr_time

    PPS_GAUGE.set(pps)
    BPS_GAUGE.set(bps)
    BASELINE_GAUGE.set(dynamic_baseline_pps)

    # Calibration warm-up - learn normal traffic baseline dynamically
    if current_calibration_tick < CALIBRATION_TICKS_REQUIRED:
        dynamic_baseline_pps = (alpha * pps) + ((1 - alpha) * dynamic_baseline_pps) if current_calibration_tick > 0 else float(pps)
        learned_max_pps = max(learned_max_pps, float(pps))
        learned_max_bps = max(learned_max_bps, float(bps))
        current_calibration_tick += 1
        print(f"CALIBRATING [{current_calibration_tick}/{CALIBRATION_TICKS_REQUIRED}] | PPS: {pps}", flush=True)
        execute_mitigation(0, pps, is_safe=True)
        continue

    # Adaptive thresholds based on learned baseline
    anomaly_threshold = max(learned_max_pps * 1.5, dynamic_baseline_pps * 3.0)
    anomaly_threshold = max(100.0, anomaly_threshold)
    critical_threshold = anomaly_threshold * 20.0
    is_critical_surge = pps >= critical_threshold

    if pps < anomaly_threshold:
        dynamic_baseline_pps = (alpha * pps) + ((1 - alpha) * dynamic_baseline_pps)
        if pps > 10:
            print(f"NORMAL (PPS: {pps} | Threshold: {int(anomaly_threshold)})", flush=True)
        ATTACK_GAUGE.set(0)
        CONFIDENCE_GAUGE.set(0)
        # Notify the mitigation engine that traffic is strictly safe
        execute_mitigation(0, pps, is_safe=True)
        continue

    # Feature engineering for ML models
    avg_packet_size = 0 if pps == 0 else bps / pps
    features_raw = [[pps, bps, ip_entropy, avg_packet_size]]
    features_scaled = scaler.transform(features_raw)
    features_tensor = torch.tensor(features_scaled, dtype=torch.float32)

    # Ensemble evaluation - DNN + Random Forest + Isolation Forest
    with torch.inference_mode():
        dnn_conf = dnn_model(features_tensor).item()
        
    # RF and ISO
    rf_pred = rf_model.predict(features_scaled)[0]
    iso_pred = iso_model.predict(features_scaled)[0]

    CONFIDENCE_GAUGE.set(dnn_conf)

    final_status = 0
    if dnn_conf > 0.8:
        final_status = 1
    elif dnn_conf > 0.6 and rf_pred == 1 and iso_pred == -1:
        final_status = 1

    ATTACK_GAUGE.set(final_status)

    # RL Agent State Formulation
    safe_max_pps = max(learned_max_pps, 1000.0)
    safe_max_bps = max(learned_max_bps, 10000.0)
    
    norm_pps = min(1.0, pps / safe_max_pps)
    norm_bps = min(1.0, bps / safe_max_bps)
    base_pod_capacity = max(learned_max_pps * 1.2, 50.0) 
    current_cpu_load = calculate_queueing_cpu(pps, k8s_apps_v1, base_pod_capacity)
    
    # State: [PPS (Norm), BPS (Norm), CPU Load, ML_Threat_Score]
    rl_state = torch.tensor([[norm_pps, norm_bps, current_cpu_load, dnn_conf]], dtype=torch.float32)
    
    with torch.inference_mode():
        action = torch.argmax(rl_agent(rl_state)).item()

    calculated_delta = min(3, max(1, int((pps / anomaly_threshold))))

    mitigation = execute_mitigation(action, pps, target_ip=potential_attacker_ip, target_replicas_delta=calculated_delta, is_critical=is_critical_surge, is_safe=False)
    
    if mitigation not in ("OBSERVING", "COOLDOWN", "MONITORING"):
        current_replicas = 1
        try:
             current_replicas = k8s_apps_v1.read_namespaced_deployment(name=SCALING_TARGET, namespace=NAMESPACE).spec.replicas
        except: pass
        print(f"[MITIGATION] Action: {mitigation} | PPS: {pps} | Target: {potential_attacker_ip} | Total Replicas: {current_replicas}", flush=True)
