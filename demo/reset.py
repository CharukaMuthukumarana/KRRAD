import subprocess
import time
import sys

def run_command(cmd):
    try:
        # Run command and hide output unless there is an error
        subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print(f"⚠️  Warning: Command failed (maybe it was already done?): {cmd}")

print("🔄 KRRAD: System Reset & Cleanup")
print("--------------------------------------------------")

# 1. Reset Scaling (Target -> 1 Replica)
print("📉 Scaling down 'krrad-target' to 1 replica...")
run_command("kubectl scale deployment krrad-target --replicas=1")

# 2. Unblock IPs (Restart Sensor)
print("🧹 Clearing Blocklists (Restarting Sensors)...")
run_command("kubectl delete pod -n kube-system -l app=krrad-sensor")

# 3. Wait for Readiness
print("⏳ Waiting for system to come back online...")
print("   - Waiting for Sensor...")
# specific command to wait until the new pods are actually 'Ready'
try:
    subprocess.run("kubectl wait --for=condition=ready pod -n kube-system -l app=krrad-sensor --timeout=60s", 
                   shell=True, check=True, stdout=subprocess.DEVNULL)
except:
    # If wait fails, just sleep a bit more
    time.sleep(5)

print("   - Waiting for Target...")
try:
    subprocess.run("kubectl wait --for=condition=ready pod -l app=krrad-target --timeout=60s", 
                   shell=True, check=True, stdout=subprocess.DEVNULL)
except:
    pass

print("--------------------------------------------------")
print("✅ SYSTEM RESET COMPLETE. Ready for next test.")