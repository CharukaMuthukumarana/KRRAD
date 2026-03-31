### KRRAD: Kubernetes-Native AI DDoS Defense Framework
KRRAD is an autonomous, self-learning cybersecurity framework designed to defend Kubernetes clusters against volumetric DDoS attacks. It utilizes an Ensemble Machine Learning pipeline (DNN, Random Forest, Isolation Forest) for threat detection, a Deep Reinforcement Learning (DQN) agent for proportional Horizontal Pod Autoscaling (HPA), and eBPF for instant, kernel-level packet dropping.

GitHub Link: https://github.com/CharukaMuthukumarana/KRRAD

Dataset: https://www.kaggle.com/datasets/dhoogla/cicddos2019/data

**KRRAD** is an autonomous security framework designed to detect and mitigate Distributed Denial of Service (DDoS) attacks in Kubernetes environments. It utilizes **eBPF (Extended Berkeley Packet Filter)** for high-performance telemetry and a hybrid **Machine Learning / Reinforcement Learning** engine for intelligent decision-making.

Docker installed and configured.

Python 3.10+

Terraform (for distributed attack simulations).

## Installation & Setup
1. Enable Kubernetes Metrics Server
KRRAD's Reinforcement Learning agent requires real-time cluster metrics to scale pods proportionally.


wget https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
sed -i 's/- args:/- args:\n        - --kubelet-insecure-tls/' components.yaml
kubectl apply -f components.yaml
Wait ~60 seconds for metrics to become available (kubectl top pods -A).

2. Deploy KRRAD Core Services

# Build and deploy the AI Controller and eBPF Sensor nodes:

cd KRRAD/controller
sudo docker build -t krrad-controller:latest .
kubectl rollout restart deployment krrad-controller


3. Launch the AI Defense Hub (Dashboard)
The UI requires the Flask Management API to bridge backend execution with the Streamlit frontend.

# Start the Management API (Background Process):

pkill -f management_api.py
python3 ~/KRRAD/ui/management_api.py &

# Start the Streamlit Dashboard:

streamlit run ~/KRRAD/ui/dashboard.py
The dashboard will be accessible via port 8501 (e.g., http://<YOUR_VM_IP>:8501).


## Running Attack Simulations

# Option A: Via the KRRAD Dashboard (Recommended)
Open the KRRAD AI Defense Hub.

In the Attack Orchestration panel, click ️ Terraform Botnet.

Watch the Live Stream metrics to observe the system auto-calibrate, detect the anomaly, calculate proportional scale targets, and execute the eBPF block.

# Option B: Via the Terminal (Manual)
To manually launch a 3-node, rate-limited (~6,000 PPS) distributed SYN flood:

cd ~/botnet
terraform init
terraform apply -auto-approve

# To stop the attack and destroy the attacker VMs:

terraform destroy -auto-approve

# System Reset & Maintenance
If you need to unblock IPs, flush the eBPF maps, and reset the mitigation history:

Click  Reset System & Unblock IPs in the Dashboard.

Or manually execute: python3 ~/KRRAD/demo/reset.py

To force the AI to recalibrate its normal traffic baseline:

Click  Restart AI (Recalibrate) in the Dashboard.