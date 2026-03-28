#!/bin/bash
set -e 

echo "========================================"
echo "    🚀 Launching KRRAD Production Hub"
echo "========================================"

# Unlock Kernel Networking
sudo modprobe br_netfilter
sudo sysctl -w net.ipv4.ip_forward=1
sudo sysctl -w net.bridge.bridge-nf-call-iptables=1
sudo iptables -P FORWARD ACCEPT

# Ensure Minikube is Active
if minikube status --format='{{.Host}}' | grep -q "Running"; then
    echo "Minikube is running."
else
    echo "Starting Minikube..."
    sudo minikube start --driver=none
    sudo chown -R $USER $HOME/.kube $HOME/.minikube
    sed -i "s|/root|/home/$USER|g" $HOME/.kube/config
fi

sudo iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {print $5}') -j MASQUERADE || true
kubectl rollout restart daemonset kube-proxy -n kube-system

# Deploy KRRAD Core Resources
echo "[3/5] Deploying Core Resources..."
kubectl apply -f /home/charuka2002buss/KRRAD/monitor/service.yaml
kubectl apply -f /home/charuka2002buss/KRRAD/monitor/daemonset.yaml
kubectl apply -f /home/charuka2002buss/KRRAD/controller/deployment.yaml
if [ -f "/home/charuka2002buss/KRRAD/controller/monitoring.yaml" ]; then
    kubectl apply -f /home/charuka2002buss/KRRAD/controller/monitoring.yaml
fi

# Stability & Service Automation
echo "Waiting for stability (Sleep 40)..."
sleep 40

echo "🔄 Syncing Grafana Dashboards..."
kubectl delete pod -l app.kubernetes.io/name=grafana --ignore-not-found
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=grafana --timeout=120s

echo "🚀 Launching Background APIs & Services..."

# Port Forward for Grafana (Port 3000)
pkill -f "port-forward" || true
nohup kubectl port-forward deployment/monitoring-grafana --address 0.0.0.0 3000:3000 > /home/charuka2002buss/KRRAD/ui/grafana_forward.log 2>&1 &

# Launch Management API (Port 8000) - FOR CLOUD UI
pkill -f "management_api.py" || true
nohup python3 /home/charuka2002buss/KRRAD/ui/management_api.py > /home/charuka2002buss/KRRAD/ui/api.log 2>&1 &

echo "========================================"
echo "✅ SYSTEM FULLY ACTIVE"
echo "Management API: http://$(curl -s ifconfig.me):8000"
echo "Grafana Dashboard: http://$(curl -s ifconfig.me):3000"
echo "========================================"
