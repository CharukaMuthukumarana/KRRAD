from flask import Flask, jsonify, request
import subprocess
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
            if status != "Running": 
                health_stat = f"❌ {status}"
            else:
                try:
                    r, t = ready.split('/')
                    health_stat = "✅ Ready" if r == t else "⚠️ Partial/Crashing"
                except:
                    health_stat = "UNKNOWN"
            pods.append({"Namespace": ns, "Pod": name, "Ready": ready, "Status": status, "Health": health_stat})
    return jsonify({"pods": pods, "raw": output})

@app.route('/logs', methods=['GET'])
def logs():
    return jsonify({"logs": subprocess.getoutput("kubectl logs --tail=20 -l app=krrad-controller")})

@app.route('/history', methods=['GET'])
def get_history():
    global mitigation_history, seen_logs
    logs = subprocess.getoutput("kubectl logs --tail=100 -l app=krrad-controller")
    for line in logs.split('\n'):
        if "Action: BLOCKING" in line or "Action: SCALING" in line:
            if line not in seen_logs:
                seen_logs.add(line)
                action = "SCALING" if "SCALING" in line else "BLOCKING"
                pps_match = re.search(r"PPS: (\d+)", line)
                pps = pps_match.group(1) if pps_match else "Unknown"
                mitigation_history.append({
                    "id": len(mitigation_history) + 1,
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                    "action": action,
                    "pps": pps,
                    "feedback": "Awaiting Admin Review"
                })
    return jsonify(mitigation_history[::-1])

@app.route('/submit-feedback', methods=['POST'])
def feedback():
    data = request.json
    action_id = data.get("id")
    val = data.get("value")
    for item in mitigation_history:
        if item["id"] == action_id:
            item["feedback"] = val
            break
    return jsonify({"status": "updated"})

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

# --- NEW: Cluster Auto-Heal Endpoint ---
@app.route('/heal', methods=['POST'])
def heal():
    # 1. Nuke corrupted Prometheus PVCs (Fixes the 1/2 issue permanently)
    subprocess.getoutput("kubectl delete pvc -l app.kubernetes.io/name=prometheus -n default --ignore-not-found")
    
    # 2. Find and delete ANY pod that is not fully healthy
    cmd = "kubectl get pods -A | awk 'NR>1 {split($3,a,\"/\"); if(a[1]!=a[2] || $4!=\"Running\") print $2 \" -n \" $1}' | xargs -L 1 kubectl delete pod --ignore-not-found"
    output = subprocess.getoutput(cmd)
    
    return jsonify({"output": "Cluster Auto-Heal Executed. Corrupted volumes cleared and unhealthy pods restarted."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
