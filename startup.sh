#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status

echo "========================================"
echo "   🚀 Launching KRRAD Production (Cloud Mode)"
echo "========================================"

# 1. Check Minikube
echo "[1/3] Ensuring Cluster is Active..."
if minikube status --format='{{.Host}}' | grep -q "Running"; then
    echo "      ✅ Minikube is running."
else
    echo "      🔻 Minikube is stopped. Starting..."
    # We use the 'none' driver for Cloud VMs (Bare Metal)
    sudo minikube start --driver=none
    
    # Fix permissions immediately after start
    sudo chown -R $USER $HOME/.kube $HOME/.minikube
    sed -i "s|/root|/home/$USER|g" $HOME/.kube/config
fi

# 2. Deploy Resources
# Kubernetes will now download your 'charuka2002/...' images from Docker Hub automatically.
echo "[2/3] Deploying Resources..."
kubectl apply -f monitor/service.yaml
kubectl apply -f monitor/daemonset.yaml
kubectl apply -f controller/deployment.yaml

# Deploy Monitoring Stack (if it exists)
if [ -f "controller/monitoring.yaml" ]; then
    kubectl apply -f controller/monitoring.yaml
fi

# 3. Permissions
echo "[3/3] Configuring Permissions..."
kubectl create clusterrolebinding krrad-admin-default --clusterrole=cluster-admin --serviceaccount=default:default --dry-run=client -o yaml | kubectl apply -f -

echo "========================================"
echo "✅ System Launch Initiated."
echo "   Wait 60s, then check status: kubectl get pods"
echo "========================================"

echo "🌍 Exposing Grafana..."
# Ensure the service exists first (it might take a second after helm install)
kubectl patch svc monitoring-grafana -p '{"spec": {"type": "NodePort"}}' || true

# Print the URL for you
NODE_PORT=$(kubectl get svc monitoring-grafana -o=jsonpath='{.spec.ports[0].nodePort}')
EXT_IP=$(curl -s ifconfig.me)
echo "✅ Grafana is available at: http://$EXT_IP:$NODE_PORT"
