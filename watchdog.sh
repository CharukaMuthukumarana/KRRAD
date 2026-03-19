#!/bin/bash
echo "🛡️ KRRAD Watchdog Started. Monitoring cluster health..."

while true; do
    # Sleep for 60 seconds between checks to avoid overloading the CPU
    sleep 60

    # 1. Find pods that are explicitly crashed (CrashLoopBackOff, Error)
    CRASHED=$(kubectl get pods -A | awk '/CrashLoopBackOff|Error/ {print $2 " -n " $1}')
    
    if [ ! -z "$CRASHED" ]; then
        echo "[$(date)] ⚠️ Watchdog found crashed pods. Restarting..."
        echo "$CRASHED" | xargs -L 1 kubectl delete pod --ignore-not-found
    fi

    # 2. Find pods that are "Running" but not fully "Ready" (e.g., 1/2, 2/3)
    # This specifically catches the stubborn Prometheus pod!
    UNREADY=$(kubectl get pods -A | tail -n +2 | awk '$4 == "Running" && $3 ~ /^([0-9]+)\/([0-9]+)$/ { split($3, a, "/"); if (a[1] != a[2]) print $2 " -n " $1 }')
    
    if [ ! -z "$UNREADY" ]; then
        echo "[$(date)] ⚠️ Watchdog found stuck unready pods. Restarting..."
        echo "$UNREADY" | xargs -L 1 kubectl delete pod --ignore-not-found
    fi
done
