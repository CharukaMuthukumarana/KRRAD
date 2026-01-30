import time
import requests
import joblib
import torch
import torch.nn as nn
import numpy as np
from prometheus_client import start_http_server, Gauge
import warnings
# Silence the "feature names" warning from sklearn
warnings.filterwarnings("ignore", category=UserWarning)

# --- PROMETHEUS METRICS ---
PPS_GAUGE = Gauge('krrad_traffic_pps', 'Current Packets Per Second')
BPS_GAUGE = Gauge('krrad_traffic_bps', 'Current Bytes Per Second')
# Status: 0=Safe, 1=Confirmed Attack, 2=Suspicious (Anomaly)
ATTACK_GAUGE = Gauge('krrad_attack_status', 'System Threat Status')
CONFIDENCE_GAUGE = Gauge('krrad_ai_confidence', 'Ensemble Confidence Score')

# --- CONFIG ---
SENSOR_URL = "http://krrad-sensor.kube-system:5000"
MODELS_DIR = "/app/models"

# --- DEFINE DEEP LEARNING MODEL CLASS ---
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

# --- LOAD THE ENSEMBLE ---
print("Initializing KRRAD Multi-Model Ensemble...")
try:
    # 1. Load Scaler (Required for DNN)
    scaler = joblib.load(f'{MODELS_DIR}/scaler.pkl')
    
    # 2. Load Deep Learning Model (DNN)
    dnn_model = KRRAD_DNN(input_dim=4)
    dnn_model.load_state_dict(torch.load(f'{MODELS_DIR}/lstm_model.pth', map_location=torch.device('cpu')))
    dnn_model.eval()
    
    # 3. Load Random Forest (RF)
    rf_model = joblib.load(f'{MODELS_DIR}/rf_model_big.pkl')
    
    # 4. Load Isolation Forest (ISO)
    iso_model = joblib.load(f'{MODELS_DIR}/iso_model_big.pkl')
    
    print("✅ ENSEMBLE LOADED: [DNN + Random Forest + Isolation Forest]")
except Exception as e:
    print(f"❌ CRITICAL LOAD ERROR: {e}")
    exit(1)

def get_traffic_stats():
    try:
        r = requests.get(f"{SENSOR_URL}/metrics", timeout=1)
        return r.json()
    except:
        return None

# --- MAIN LOOP ---
start_http_server(8000)
print("🚀 Controller Running with Ensemble Logic...")

last_packets = 0
last_bytes = 0

while True:
    time.sleep(1)
    
    data = get_traffic_stats()
    if not data: continue
    
    # 1. Calculate Live Metrics
    curr_packets = data.get('packets', 0)
    curr_bytes = data.get('bytes', 0)
    
    pps = max(0, curr_packets - last_packets)
    bps = max(0, curr_bytes - last_bytes)
    
    last_packets = curr_packets
    last_bytes = curr_bytes
    
    # 2. Feature Engineering (Must match training data!)
    # [PPS, Bytes, Packets, Avg_Size]
    avg_packet_size = 0 if pps == 0 else bps / pps
    
    # Raw features for RF and ISO
    features_raw = [[pps, bps, pps, avg_packet_size]]
    
    # Scaled features for DNN
    features_scaled = scaler.transform(features_raw)
    features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
    
    # --- 3. GET VOTES FROM ALL MODELS ---
    
    # Vote A: Deep Neural Network (0.0 to 1.0)
    with torch.no_grad():
        dnn_conf = dnn_model(features_tensor).item()
        
    # Vote B: Random Forest (0 or 1)
    rf_pred = rf_model.predict(features_raw)[0]
    
    # Vote C: Isolation Forest (1=Normal, -1=Anomaly)
    iso_pred = iso_model.predict(features_raw)[0]
    iso_is_anomaly = (iso_pred == -1)
    
    # --- 4. THE CONSENSUS LOGIC ---
    
    final_status = 0 # Default Safe
    
    # LOGIC 1: Confirmed Attack (Both Supervised Models Agree)
    if rf_pred == 1 and dnn_conf > 0.8:
        print(f"🚨 CONFIRMED ATTACK! (RF: Attack | DNN: {dnn_conf:.2f})")
        final_status = 1
        
    # LOGIC 2: High Probability (DNN is very sure, even if RF missed)
    elif dnn_conf > 0.95:
        print(f"⚠️ HIGH THREAT (DNN Confidence: {dnn_conf:.2f})")
        final_status = 1
        
    # LOGIC 3: Suspicious / Zero-Day (Models say safe, but IsoForest sees anomaly)
    elif iso_is_anomaly and pps > 100: # Ignore anomalies if traffic is tiny
        print(f"👀 SUSPICIOUS ANOMALY (Zero-Day Potential?)")
        final_status = 2 
        
    else:
        print(f"✅ Safe Traffic (PPS: {pps} | Size: {avg_packet_size:.1f}B)")
        final_status = 0

    # Update Dashboard
    PPS_GAUGE.set(pps)
    BPS_GAUGE.set(bps)
    ATTACK_GAUGE.set(final_status)
    CONFIDENCE_GAUGE.set(dnn_conf)