#!/bin/bash
set -e # Exit if any command fails

echo "========================================"
echo "   🚀 KRRAD System Launch Sequence      "
echo "========================================"

# 1. Smart Minikube Check
echo "[1/5] Checking Minikube Status..."
if minikube status --format='{{.Host}}' | grep -q "Running"; then
    echo "      ✅ Minikube is already running."
    echo "      🔄 Refreshing connection (fixing TLS)..."
    minikube update-context > /dev/null
else
    echo "      🔻 Minikube is stopped. Starting (may download image)..."
    minikube start
fi

# 2. Configure Docker Environment
echo "[2/5] Configuring Docker Env..."
eval $(minikube -p minikube docker-env)

# 3. Build Docker Images
echo "[3/5] Building Docker Images..."
echo "      Building Sensor (eBPF)..."
docker build -t krrad-sensor:latest -f monitor/Dockerfile monitor/ > /dev/null
echo "      Building Controller (AI Brain)..."
docker build -t krrad-controller:latest -f controller/Dockerfile controller/ > /dev/null

# 4. Deploy to Kubernetes
echo "[4/5] Deploying Resources..."

# Deploy Sensor
kubectl apply -f monitor/service.yaml
kubectl apply -f monitor/daemonset.yaml

# Deploy Controller
kubectl apply -f controller/deployment.yaml

# Deploy Monitoring Stack (if it exists)
if [ -f "controller/monitoring.yaml" ]; then
    kubectl apply -f controller/monitoring.yaml
fi

# 5. Grant Permissions
echo "[5/5] Configuring Permissions..."
kubectl create clusterrolebinding krrad-admin-default --clusterrole=cluster-admin --serviceaccount=default:default --dry-run=client -o yaml | kubectl apply -f -

echo "========================================"
echo "✅ KRRAD System is LIVE!"
echo "   Monitor Logs: kubectl logs -f -l app=krrad-controller"
echo "========================================"