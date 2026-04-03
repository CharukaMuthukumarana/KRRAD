from flask import Flask, jsonify, request
import subprocess
import re
import datetime

app = Flask(__name__)
mitigation_history = []
seen_logs = set()
active_blocks = set()

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
    global mitigation_history, seen_logs, active_blocks
    logs = subprocess.getoutput("kubectl logs --tail=150 -l app=krrad-controller")
    for line in logs.split('\n'):
        if "[MITIGATION]" in line and line not in seen_logs:
            seen_logs.add(line)
            
            # Improved Regex to catch "INSTANT BLOCK" and IP addresses
            act_m = re.search(r"Action:\s*([^|]+)", line)
            pps_m = re.search(r"PPS:\s*(\d+)", line)
            tgt_m = re.search(r"Target:\s*([\d\.]+)", line)
            rep_m = re.search(r"Replicas:\s*(\d+)", line)
            
            action_text = act_m.group(1).strip() if act_m else "Unknown"
            target_ip = tgt_m.group(1) if tgt_m else None
            
            # If an IP is blocked, add it to our active XDP blacklist tracker
            if target_ip and ("BLOCK" in action_text):
                active_blocks.add(target_ip)
            
            mitigation_history.append({
                "id": len(mitigation_history) + 1,
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "action": action_text,
                "target/replicas": target_ip if target_ip else (f"Scale to {rep_m.group(1)}" if rep_m else "System"),
                "feedback": "Awaiting Review"
            })
    return jsonify({
        "history": mitigation_history[::-1], 
        "active_blocks": list(active_blocks)
    })

@app.route('/launch-terraform', methods=['POST'])
def launch_terraform():
    cmd = "cd /home/charuka2002buss/botnet && terraform init && terraform apply -auto-approve"
    subprocess.Popen(cmd, shell=True) # nosec
    return jsonify({"status": "Terraform botnet launching"})

@app.route('/stop-terraform', methods=['POST'])
def stop_terraform():
    cmd = "cd /home/charuka2002buss/botnet && terraform destroy -auto-approve"
    subprocess.Popen(cmd, shell=True) # nosec
    return jsonify({"status": "Terraform botnet stopping"})

@app.route('/clear-history', methods=['POST'])
def clear_history():
    global mitigation_history
    mitigation_history.clear()
    return jsonify({"status": "cleared"})

@app.route('/reset', methods=['POST'])
def reset():
    global mitigation_history, active_blocks
    mitigation_history.clear()
    active_blocks.clear()
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

@app.route('/launch-local-attack', methods=['POST'])
def launch_local_attack():
    cmd = "sudo hping3 -a 10.0.0.99 -S -p 32028 --flood 127.0.0.1"
    subprocess.Popen(cmd, shell=True) # nosec
    return jsonify({"status": "Local attack launched"})

@app.route('/stop-local-attack', methods=['POST'])
def stop_local_attack():
    subprocess.Popen("sudo pkill hping3", shell=True) # nosec
    return jsonify({"status": "Local attack stopped"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
