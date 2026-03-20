#!/bin/bash
set -e 

echo "========================================"
echo "    🚀 Launching KRRAD Production Hub"
echo "========================================"

# 1. Unlock Kernel Networking
sudo modprobe br_netfilter
sudo sysctl -w net.ipv4.ip_forward=1
sudo sysctl -w net.bridge.bridge-nf-call-iptables=1
sudo iptables -P FORWARD ACCEPT

# 2. Ensure Minikube is Active
if minikube status --format='{{.Host}}' | grep -q "Running"; then
    echo "      ✅ Minikube is running."
else
    echo "      🔻 Starting Minikube..."
    sudo minikube start --driver=none
    sudo chown -R $USER $HOME/.kube $HOME/.minikube
    sed -i "s|/root|/home/$USER|g" $HOME/.kube/config
fi

# 3. Network Routing Fixes
sudo iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {print $5}') -j MASQUERADE || true
kubectl rollout restart daemonset kube-proxy -n kube-system

# 4. Deploy KRRAD Core Resources
echo "[3/5] Deploying Core Resources..."
kubectl apply -f /home/charuka2002buss/KRRAD/monitor/service.yaml
kubectl apply -f /home/charuka2002buss/KRRAD/monitor/daemonset.yaml
kubectl apply -f /home/charuka2002buss/KRRAD/controller/deployment.yaml
[ -f "/home/charuka2002buss/KRRAD/controller/monitoring.yaml" ] && kubectl apply -f /home/charuka2002buss/KRRAD/controller/monitoring.yaml

# 5. UI & Dashboard Automation
echo "⏳ Waiting for stability..."
sleep 40

# Restart Grafana to pick up dashboards immediately
kubectl delete pod -l app.kubernetes.io/name=grafana --ignore-not-found

echo "🚀 Launching Background Services..."
# Port Forward for Grafana (Port 3000)
pkill -f "port-forward" || true
nohup kubectl port-forward deployment/monitoring-grafana --address 0.0.0.0 3000:3000 > /dev/null 2>&1 &

# Launch Streamlit Defense Hub (Port 8501)
pkill -f "streamlit" || true
nohup python3 -m streamlit run /home/charuka2002buss/KRRAD/ui/dashboard.py --server.port 8501 --server.address 0.0.0.0 > /home/charuka2002buss/KRRAD/ui/streamlit.log 2>&1 &

echo "========================================"
echo "✅ SYSTEM FULLY ACTIVE"
echo "🛡️  Defense Hub: http://$(curl -s ifconfig.me):8501"
echo "📊 Grafana:     http://$(curl -s ifconfig.me):3000"
echo "========================================"
