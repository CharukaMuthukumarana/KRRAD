#!/bin/bash

echo "========================================"
echo "    KRRAD System Shutdown Sequence    "
echo "========================================"

# 1. Delete Resources
echo "[1/2] Removing Kubernetes Resources..."
kubectl delete -f controller/deployment.yaml --ignore-not-found=true
kubectl delete -f monitor/daemonset.yaml --ignore-not-found=true
kubectl delete -f monitor/service.yaml --ignore-not-found=true

if [ -f "controller/monitoring.yaml" ]; then
    kubectl delete -f controller/monitoring.yaml --ignore-not-found=true
fi

# 2. Stop Minikube
echo "[2/2] Stopping Minikube Cluster..."
minikube stop

echo "========================================"
echo " System Shutdown Complete."
echo "========================================"