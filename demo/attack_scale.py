import subprocess
import time
import sys

def run_command(cmd):
    try: return subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
    except: return None

print("🚀 KRRAD Demo: TRUE Distributed Attack (3 Botnet Nodes)")
print("--------------------------------------------------")

# 1. Reset Sensor
print("🧹 Resetting Sensor...")
subprocess.run("kubectl delete pod -n kube-system -l app=krrad-sensor", shell=True)
time.sleep(15)

sensor_ip = run_command("kubectl get pods -n kube-system -l app=krrad-sensor -o jsonpath='{.items[0].status.podIP}'")
print(f"✅ Target: {sensor_ip}")

# 2. Get All Attackers
# The -l app=krrad-attacker selector will catch all 3 pods
attackers = run_command("kubectl get pods -l app=krrad-attacker -o jsonpath='{.items[*].metadata.name}'").split()
print(f"💀 Botnet Nodes Found: {attackers}")

# 3. Launch the Swarm
print("\n⚠️  LAUNCHING SWARM... (Press Ctrl+C to Stop)")
processes = []

try:
    for bot in attackers:
        # Each bot hits with medium speed. Combined = High Load.
        cmd = f"kubectl exec -it {bot} -- hping3 -S -p 5000 -i u1000 {sensor_ip}"
        print(f"   -> {bot} attacking...")
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL)
        processes.append(p)
    
    # Keep running
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n\n🛑 Stopping Swarm...")
    for p in processes:
        p.terminate()