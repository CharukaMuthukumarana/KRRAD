import os
import subprocess

def run_cmd(cmd):
    return subprocess.getoutput(cmd)

print("KRRAD: Clearing Blacklists and Unblocking all IPs...")

print(" Resetting DaemonSet (Enforcers)...")
os.system("kubectl rollout restart daemonset -l app=krrad-daemonset")

print("Resetting AI Controller...")
os.system("kubectl rollout restart deployment krrad-controller")

print(" All blocks cleared. Monitoring resumed.")
