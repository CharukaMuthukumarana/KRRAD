# KRRAD: Kubernetes-native Resilience and Response Against DDoS

GitHub Link: https://github.com/CharukaMuthukumarana/KRRAD

Dataset: https://www.kaggle.com/datasets/dhoogla/cicddos2019/data

**KRRAD** is an autonomous security framework designed to detect and mitigate Distributed Denial of Service (DDoS) attacks in Kubernetes environments. It utilizes **eBPF (Extended Berkeley Packet Filter)** for high-performance telemetry and a hybrid **Machine Learning / Reinforcement Learning** engine for intelligent decision-making.

---

## Quick Start (Run the System)
Use these commands to start and stop the system for demonstrations.

### 1. Start the System
If you have already built the images, follow these steps to wake up the cluster and run KRRAD.

**Step 1: Start Infrastructure**
# Start the Virtual Machine
colima start --cpu 4 --memory 8

# Start the Kubernetes Cluster
minikube start

**Step 2: deploy/Wake Up KRRAD If the pods are not running automatically, apply the configurations:**
# Deploy Sensor (The Eyes)
kubectl apply -f monitor/daemonset.yaml
kubectl apply -f monitor/service.yaml
# Deploy Controller (The Brain)
kubectl apply -f controller/deployment.yaml

**Step 3: Monitor Logs Watch the brain making decisions in real-time:**
    kubectl logs -f -l app=krrad-controller
# (Wait until you see "KRRAD Controller Started" before attacking)


### 2. Stop the System

# Stop the cluster
minikube stop
# Stop the VM
colima stop



### How to Simulate an Attack

# To demonstrate the system's reaction, you will simulate a high-velocity SYN Flood attack.
* Open a NEW Terminal window.
* Log into the hosting VM:
    colima ssh

# Launch the Attack: (Replace <IP_ADDRESS> with your Minikube IP if different)
* udo hping3 -S -p 5000 --flood <IP_ADDRESS>

# Observe Results: Switch back to your Controller Logs terminal. You should see the status change from Secure to:
!!! ATTACK DETECTED (Conf: 0.85) !!!
>> RL Decision: BLOCK IP

# Stop Attack: Press Ctrl + C in the Colima terminal.



### First-Time Installation & Build
* Only run this section if you are setting up the project from scratch or if you have changed the code.

Prerequisites
* OS: macOS (Apple Silicon M1/M2/M3)
* Virtualization: Colima
* Orchestration: Minikube
* Tools: kubectl, docker, python3, hping3

## Environment Setup
# Start Colima with sufficient resources
colima start --cpu 4 --memory 8
# Start Minikube with BPF mounting enabled
minikube start --driver=docker --container-runtime=docker \
  --mount \
  --mount-string="/sys/fs/bpf:/sys/fs/bpf" \
  --mount-string="/lib/modules:/lib/modules"

## Build Docker Images
* We must build the images inside Minikube's Docker environment so the cluster can see them.
# 1. Point shell to Minikube's Docker daemon
eval $(minikube -p minikube docker-env)
# 2. Build eBPF Sensor
docker build -t krrad-sensor:latest -f monitor/Dockerfile monitor/
# 3. Build AI Controller
docker build -t krrad-controller:latest -f controller/Dockerfile controller/





### System Architecture
1. The Sensor (eBPF/XDP)
* Location: Kernel Space (Network Interface Card driver level).
* Function: Inspects every packet before the OS handles it.
* Telemetry: Extracts PPS (Packets Per Second) and Bandwidth stats without performance overhead.
* Action: Can drop malicious packets instantly (XDP_DROP).
 
2. The Controller (Python)
* Function: Central "Brain" that aggregates data from the Sensor.
* Detection (Machine Learning):
    * Model: Random Forest Classifier.
    * Training: Trained on a balanced dataset of CICDDoS2019 + Synthetic Noise.
    * Role: Determines if an attack is happening (Probability > 0.5).
* Decision (Reinforcement Learning):
    * Model: Deep Q-Network (DQN).
    * Role: Determines the best response (Block Source, Scale Pods, or Monitor) based on reward maximization.



### Troubleshooting
1. "Minikube command not found" during build
Fix: You likely opened a new terminal. Run eval $(minikube -p minikube docker-env) again before building.

2. Attack is running but logs show 0 PPS
Fix: The attacker must target the Node IP (192.168.49.2), not the Service DNS. Use kubectl get pods -o wide to check IPs if unsure.

3. "X does not have valid feature names" warning
Fix: This is a benign warning from Scikit-Learn. It does not affect functionality and can be ignored. 

4. "Cannot connect to the Docker daemon"
Fix: eval $(minikube -p minikube docker-env)



### Get Grafana admin user password
* kubectl --namespace default get secrets monitoring-grafana -o jsonpath="{.data.admin-password}" | base64 -d ; echo

