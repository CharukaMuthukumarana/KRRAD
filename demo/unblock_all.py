import os
import subprocess

def run_cmd(cmd):
    return subprocess.getoutput(cmd)

print("🛡️  KRRAD: Clearing Blacklists and Unblocking all IPs...")

# 1. Clear eBPF Maps/Iptables by restarting the enforcers
# This forces the daemonset to flush its internal memory-based blacklists
print("🔄 Resetting DaemonSet (Enforcers)...")
os.system("kubectl rollout restart daemonset -l app=krrad-daemonset")

# 2. Reset the AI Controller state
print("🧠 Resetting AI Controller...")
os.system("kubectl rollout restart deployment krrad-controller")

print("✅ All blocks cleared. Monitoring resumed.")
