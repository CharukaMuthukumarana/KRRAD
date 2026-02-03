#!/bin/bash
set -e

echo "========================================"
echo "   🚀 Initializing KRRAD System (Final) "
echo "========================================"

# --- FIX 1: ENSURE CORRECT IMAGE VERSION ---
# We force the local file to use v1.3 so we don't load the buggy v1.0
sed -i 's|image: charuka2002/krrad-sensor:v.*|image: charuka2002/krrad-sensor:v1.3|' monitor/daemonset.yaml

# --- FIX 2: CREATE CONTROLLER SERVICE IF MISSING ---
# The dashboard needs this "Door" to open
cat << 'yaml' > controller/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: krrad-controller-metrics
  namespace: default
  labels:
    app: krrad-controller
spec:
  selector:
    app: krrad-controller
  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000
      name: metrics
yaml

# --- STARTUP SEQUENCE ---

echo "[1/6] Booting Kubernetes..."
# We use 'sudo' because the 'none' driver requires root access to Docker
sudo minikube start --driver=none

echo "[2/6] Fixing Permissions..."
# Move config from Root to User folder so kubectl works
sudo cp -r /root/.kube $HOME/ 2>/dev/null || true
sudo cp -r /root/.minikube $HOME/ 2>/dev/null || true
sudo chown -R $USER $HOME/.kube $HOME/.minikube
# Ensure the config points to the user directory, not root
sed -i "s|/root|/home/$USER|g" $HOME/.kube/config

echo "[3/6] Deploying KRRAD Components..."
kubectl apply -f monitor/service.yaml
kubectl apply -f monitor/daemonset.yaml
kubectl apply -f controller/deployment.yaml
kubectl apply -f controller/service.yaml  # Applying the service we just created

echo "[4/6] Linking Brain to Eyes..."
# Wait for the Sensor Service to get an IP address
sleep 10
NEW_SENSOR_IP=$(kubectl get svc -n kube-system krrad-sensor -o jsonpath='{.spec.clusterIP}')
echo "      ℹ️  Sensor IP found: $NEW_SENSOR_IP"

if [ -z "$NEW_SENSOR_IP" ]; then
    echo "      ⚠️  Warning: IP not ready. Waiting 5s..."
    sleep 5
    NEW_SENSOR_IP=$(kubectl get svc -n kube-system krrad-sensor -o jsonpath='{.spec.clusterIP}')
fi

# Update deployment.yaml with the new Sensor IP (Fixing the connection)
sed -i "s|value: \"http://[0-9.]*:5000\"|value: \"http://$NEW_SENSOR_IP:5000\"|g" controller/deployment.yaml

# Apply the connection fix and restart the brain
kubectl apply -f controller/deployment.yaml > /dev/null
kubectl delete pod -l app=krrad-controller --grace-period=0 --force 2>/dev/null || true

echo "[5/6] Waiting for Green Lights..."
kubectl wait --for=condition=ready pod -l app=krrad-sensor -n kube-system --timeout=120s
kubectl wait --for=condition=ready pod -l app=krrad-controller --timeout=120s

echo "========================================"
echo "✅ SYSTEM IS LIVE! 🚀"
echo "========================================"
echo "👉 NEXT STEP: Run this command for the dashboard:"
echo "   kubectl port-forward --address 0.0.0.0 svc/krrad-controller-metrics 8000:8000"
echo "To Get Logs: kubectl logs -l app=krrad-controller -f"
