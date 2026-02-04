# demo/attack_single.py
import subprocess, sys

def run_command(cmd):
    try: return subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
    except: return None

print("🚀 Blocking Test (Target: < 250 PPS)")
sensor_ip = run_command("kubectl get pods -n kube-system -l app=krrad-sensor -o jsonpath='{.items[0].status.podIP}'")
attacker_pod = run_command("kubectl get pods -l app=krrad-attacker -o jsonpath='{.items[0].metadata.name}'")

# -i u10000 = 100 PPS. Safe range for Blocking.
cmd = f"kubectl exec -it {attacker_pod} -- hping3 -S -p 5000 -i u10000 {sensor_ip}"
subprocess.run(cmd, shell=True)