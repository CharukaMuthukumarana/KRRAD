#!/bin/bash
echo "️ KRRAD Watchdog Started. Monitoring strict cluster health..."

while true; do
    sleep 60
    UNHEALTHY=$(kubectl get pods -A | awk 'NR>1 {split($3,a,"/"); if ($4=="CrashLoopBackOff" || $4=="Error" || a[1]!=a[2]) print $2 " -n " $1}')
    
    if [ ! -z "$UNHEALTHY" ]; then
        echo "[$(date)] ️ Watchdog found unhealthy pods. Executing self-healing..."
        echo "$UNHEALTHY" | xargs -L 1 kubectl delete pod --ignore-not-found
    fi
done
