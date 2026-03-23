from flask import Flask, jsonify, request
import subprocess
import requests
import re
import datetime

app = Flask(__name__)
mitigation_history = []
seen_logs = set()

@app.route('/health', methods=['GET'])
def health():
    output = subprocess.getoutput("kubectl get pods -A")
    pods = []
    for line in output.strip().split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 6:
            ns, name, ready, status = parts[0], parts[1], parts[2], parts[3]
            health_stat = f"✅ Ready" if status == "Running" and ready.split('/')[0] == ready.split('/')[1] else f"❌ {status}"
            pods.append({"Namespace": ns, "Pod": name, "Ready": ready, "Status": status, "Health": health_stat})
    return jsonify({"pods": pods, "raw": output})

@app.route('/logs', methods=['GET'])
def logs():
    return jsonify({"logs": subprocess.getoutput("kubectl logs --tail=20 -l app=krrad-controller")})

@app.route('/history', methods=['GET'])
def get_history():
    global mitigation_history, seen_logs
    logs = subprocess.getoutput("kubectl logs --tail=150 -l app=krrad-controller")
    for line in logs.split('\n'):
        if "[MITIGATION]" in line and line not in seen_logs:
            seen_logs.add(line)
            act_m = re.search(r"Action: (\w+)", line)
            pps_m = re.search(r"PPS: (\d+)", line)
            tgt_m = re.search(r"Target: ([\d\.]+)", line)
            rep_m = re.search(r"Replicas: (\d+)", line)
            
            mitigation_history.append({
                "id": len(mitigation_history) + 1,
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "action": act_m.group(1) if act_m else "Unknown",
                "pps": pps_m.group(1) if pps_m else "0",
                "target/replicas": tgt_m.group(1) if tgt_m else (f"Scale to {rep_m.group(1)}" if rep_m else "System"),
                "feedback": "Awaiting Review"
            })
    return jsonify(mitigation_history[::-1])

# --- TERRAFORM ENDPOINTS ---
@app.route('/launch-terraform', methods=['POST'])
def launch_terraform():
    cmd = "cd /home/charuka2002buss/botnet && terraform init && terraform apply -auto-approve"
    subprocess.Popen(cmd, shell=True)
    return jsonify({"status": "Terraform botnet launching"})

@app.route('/stop-terraform', methods=['POST'])
def stop_terraform():
    cmd = "cd /home/charuka2002buss/botnet && terraform destroy -auto-approve"
    subprocess.Popen(cmd, shell=True)
    return jsonify({"status": "Terraform botnet stopping"})

@app.route('/simulate-swarm', methods=['POST'])
def simulate_swarm():
    target_ip = subprocess.getoutput("hostname -I | awk '{print $1}'")
    cmd = f"docker run --rm -d --name swarm_flood --net=host debian:bookworm-slim sh -c 'apt-get update && apt-get install -y hping3 && hping3 -S --flood --rand-source -p 32028 {target_ip}'"
    subprocess.Popen(cmd, shell=True)
    return jsonify({"status": "Swarm simulation started"})

@app.route('/stop-swarm', methods=['POST'])
def stop_swarm():
    subprocess.getoutput("docker rm -f swarm_flood")
    return jsonify({"status": "stopped"})

@app.route('/clear-history', methods=['POST'])
def clear_history():
    global mitigation_history, seen_logs
    mitigation_history.clear()
    seen_logs.clear()
    return jsonify({"status": "cleared"})

@app.route('/reset', methods=['POST'])
def reset():
    global mitigation_history, seen_logs
    mitigation_history.clear()
    seen_logs.clear()
    return jsonify({"output": subprocess.getoutput("python3 /home/charuka2002buss/KRRAD/demo/reset.py")})

@app.route('/restart-ai', methods=['POST'])
def restart():
    return jsonify({"output": subprocess.getoutput("kubectl rollout restart deployment krrad-controller")})

@app.route('/heal', methods=['POST'])
def heal():
    subprocess.getoutput("kubectl delete pvc -l app.kubernetes.io/name=prometheus -n default --ignore-not-found")
    subprocess.getoutput("kubectl get pods -A | awk 'NR>1 {split($3,a,\"/\"); if(a[1]!=a[2] || $4!=\"Running\") print $2 \" -n \" $1}' | xargs -L 1 kubectl delete pod --ignore-not-found")
    return jsonify({"output": "Cluster Auto-Heal Executed."})

@app.route('/submit-feedback', methods=['POST'])
def feedback():
    data = request.json
    for item in mitigation_history:
        if item["id"] == data.get("id"):
            item["feedback"] = data.get("value")
            break
    return jsonify({"status": "updated"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
