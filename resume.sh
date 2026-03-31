#!/bin/bash
set -e

echo "========================================"
echo "    Initializing KRRAD System (Final) "
echo "========================================"

sed -i 's|image: charuka2002/krrad-sensor:v.*|image: charuka2002/krrad-sensor:v1.3|' monitor/daemonset.yaml

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


echo "[1/6] Booting Kubernetes..."
sudo minikube start --driver=none

echo "[2/6] Fixing Permissions..."
sudo cp -r /root/.kube $HOME/ 2>/dev/null || true
sudo cp -r /root/.minikube $HOME/ 2>/dev/null || true
sudo chown -R $USER $HOME/.kube $HOME/.minikube
sed -i "s|/root|/home/$USER|g" $HOME/.kube/config

echo "[3/6] Deploying KRRAD Components..."
kubectl apply -f monitor/service.yaml
kubectl apply -f monitor/daemonset.yaml
kubectl apply -f controller/deployment.yaml
kubectl apply -f controller/service.yaml

echo "[4/6] Linking Brain to Eyes..."
sleep 10
NEW_SENSOR_IP=$(kubectl get svc -n kube-system krrad-sensor -o jsonpath='{.spec.clusterIP}')
echo "      ℹ️  Sensor IP found: $NEW_SENSOR_IP"

if [ -z "$NEW_SENSOR_IP" ]; then
    echo "      ️  Warning: IP not ready. Waiting 5s..."
    sleep 5
    NEW_SENSOR_IP=$(kubectl get svc -n kube-system krrad-sensor -o jsonpath='{.spec.clusterIP}')
fi

sed -i "s|value: \"http://[0-9.]*:5000\"|value: \"http://$NEW_SENSOR_IP:5000\"|g" controller/deployment.yaml

kubectl apply -f controller/deployment.yaml > /dev/null
kubectl delete pod -l app=krrad-controller --grace-period=0 --force 2>/dev/null || true

echo "[5/6] Waiting for Green Lights..."
kubectl wait --for=condition=ready pod -l app=krrad-sensor -n kube-system --timeout=120s
kubectl wait --for=condition=ready pod -l app=krrad-controller --timeout=120s

echo "========================================"
echo " SYSTEM IS LIVE! "
echo "========================================"
echo " NEXT STEP: Run this command for the dashboard:"
echo "   kubectl port-forward --address 0.0.0.0 svc/krrad-controller-metrics 8000:8000"
echo "To Get Logs: kubectl logs -l app=krrad-controller -f"
