#!/bin/bash

echo "========================================"
echo "   🛑 Stopping KRRAD Application Only   "
echo "========================================"

# 1. Delete the "Brain" (Controller)
echo "[1/3] Removing Controller..."
kubectl delete -f controller/deployment.yaml --ignore-not-found=true

# 2. Delete the "Eyes" (Sensor)
echo "[2/3] Removing Sensor..."
kubectl delete -f monitor/daemonset.yaml --ignore-not-found=true
kubectl delete -f monitor/service.yaml --ignore-not-found=true

# 3. Delete Monitoring Stack (if applicable)
if [ -f "controller/monitoring.yaml" ]; then
    echo "[3/3] Removing Monitoring Stack..."
    kubectl delete -f controller/monitoring.yaml --ignore-not-found=true
fi

echo "========================================"
echo "✅ Application Stopped."
echo "   Minikube is still active. "
echo "   Run ./startup.sh to restart INSTANTLY."
echo "========================================"