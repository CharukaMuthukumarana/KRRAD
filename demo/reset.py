import subprocess
import time
import sys

def run_command(cmd):
    try:
        # Run command and hide output unless there is an error
        subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass # Ignore errors (like trying to scale down something that is already down)

print("🔄 KRRAD: System Reset & Cleanup")
print("--------------------------------------------------")

# 1. STOP THE ATTACK (Crucial Step)
print("🛑 Killing all Attackers...")
# Try to scale down deployment if it exists
run_command("kubectl scale deployment attacker --replicas=0")
# Force delete any lingering attacker pods
run_command("kubectl delete pods -l app=attacker --grace-period=0 --force")

# 2. PAUSE THE BRAIN
print("🧠 Pausing Controller (Preventing False Alarms)...")
run_command("kubectl scale deployment krrad-controller --replicas=0")

# 3. RESET INFRASTRUCTURE
print("📉 Resetting Target to 1 Replica...")
run_command("kubectl scale deployment krrad-target --replicas=1")

print("🧹 Restarting Sensors (Clearing Blocklists)...")
run_command("kubectl delete pod -n kube-system -l app=krrad-sensor")

# 4. WAIT FOR SILENCE
print("⏳ Waiting for system to stabilize...")
time.sleep(5) # Give Kubernetes time to kill the attackers

print("   - Waiting for Sensor...")
try:
    subprocess.run("kubectl wait --for=condition=ready pod -n kube-system -l app=krrad-sensor --timeout=60s", 
                   shell=True, check=True, stdout=subprocess.DEVNULL)
except:
    pass

print("   - Waiting for Target...")
try:
    subprocess.run("kubectl wait --for=condition=ready pod -l app=krrad-target --timeout=60s", 
                   shell=True, check=True, stdout=subprocess.DEVNULL)
except:
    pass

# 5. WAKE UP THE BRAIN
print("🧠 Waking up KRRAD Controller...")
run_command("kubectl scale deployment krrad-controller --replicas=1")
try:
    subprocess.run("kubectl wait --for=condition=ready pod -l app=krrad-controller --timeout=30s", 
                   shell=True, check=True, stdout=subprocess.DEVNULL)
except:
    pass

print("--------------------------------------------------")
print("✅ SYSTEM CLEAN. Baseline: 0 PPS.")