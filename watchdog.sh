#!/bin/bash
echo "🛡️ KRRAD Watchdog Started. Monitoring cluster health..."

while true; do
    sleep 60
    # Find only pods that have explicitly crashed
    CRASHED=$(kubectl get pods -A | awk '/CrashLoopBackOff|Error/ {print $2 " -n " $1}')
    
    if [ ! -z "$CRASHED" ]; then
        echo "[$(date)] ⚠️ Watchdog found crashed pods. Restarting..."
        echo "$CRASHED" | xargs -L 1 kubectl delete pod --ignore-not-found
    fi
done
