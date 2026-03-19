#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status

echo "========================================"
echo "   🚀 Launching KRRAD Production (Cloud Mode)"
echo "========================================"

# 1. Check & Start Minikube FIRST
echo "[1/5] Ensuring Cluster is Active..."
if minikube status --format='{{.Host}}' | grep -q "Running"; then
    echo "      ✅ Minikube is running."
else
    echo "      🔻 Minikube is stopped. Starting..."
    sudo minikube start --driver=none
    
    sudo chown -R $USER $HOME/.kube $HOME/.minikube
    sed -i "s|/root|/home/$USER|g" $HOME/.kube/config
fi

# 2. Force Cloud Network & Kernel Overrides (Must run AFTER Minikube starts)
echo "[2/5] Injecting Kernel Modules & Fixing Network Routing..."
sudo modprobe br_netfilter || true
sudo sysctl -w net.bridge.bridge-nf-call-iptables=1 || true
sudo iptables -P FORWARD ACCEPT
sudo iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {print $5}') -j MASQUERADE || true

# Force the cluster to recognize the newly injected kernel modules
kubectl rollout restart daemonset kube-proxy -n kube-system
kubectl rollout restart -n kube-system deployment/coredns

# 3. Deploy Resources
echo "[3/5] Deploying KRRAD Resources..."
kubectl apply -f monitor/service.yaml
kubectl apply -f monitor/daemonset.yaml
kubectl apply -f controller/deployment.yaml

if [ -f "controller/monitoring.yaml" ]; then
    kubectl apply -f controller/monitoring.yaml
fi

# 4. Permissions & Wake Up Monitoring Pods
echo "[4/5] Configuring Permissions & Waking Pods..."
kubectl create clusterrolebinding krrad-admin-default --clusterrole=cluster-admin --serviceaccount=default:default --dry-run=client -o yaml | kubectl apply -f -

kubectl delete pod -l app.kubernetes.io/name=grafana --ignore-not-found > /dev/null
kubectl delete pod -l app=kube-prometheus-stack-operator --ignore-not-found > /dev/null

# 5. KRRAD Auto-Healer (Watchdog)
echo "[5/5] Launching Continuous Auto-Healer (Watchdog)..."
pkill -f "watchdog.sh" || true 
nohup ./watchdog.sh > watchdog.log 2>&1 &

echo "========================================"
echo "✅ System Launch Complete. Watchdog is ACTIVE."
echo "   Wait 60s for full stabilization, then check: kubectl get pods"
echo "========================================"

echo "🌍 Exposing Grafana..."
kubectl patch svc monitoring-grafana -p '{"spec": {"type": "NodePort"}}' || true

NODE_PORT=$(kubectl get svc monitoring-grafana -o=jsonpath='{.spec.ports[0].nodePort}')
EXT_IP=$(curl -s ifconfig.me)
echo "✅ Grafana is available at: http://$EXT_IP:$NODE_PORT"
