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
    global mitigation_history
    # FIX: We ONLY clear the history array. We leave seen_logs intact 
    # so the API doesn't re-parse old logs as "new" events!
    mitigation_history.clear()
    return jsonify({"status": "cleared"})

# --- NEW: Local Swarm Simulator (Bypasses GCP Spoofing Filters) ---
@app.route('/simulate-swarm', methods=['POST'])
def simulate_swarm():
    # Uses a tiny, fast Docker container to launch a swarm locally
    cmd = "docker run --rm -d --name swarm_flood --net=host alpine sh -c 'apk add --no-cache hping3 && hping3 -S --flood -p 32028 127.0.0.1'"
    subprocess.Popen(cmd, shell=True)
    return jsonify({"status": "Swarm simulated locally"})

@app.route('/stop-swarm', methods=['POST'])
def stop_swarm():
    subprocess.getoutput("docker rm -f swarm_flood")
    return jsonify({"status": "stopped"})

@app.route('/reset', methods=['POST'])
def reset():
    global mitigation_history
    mitigation_history.clear()
    return jsonify({"output": subprocess.getoutput("python3 /home/charuka2002buss/KRRAD/demo/reset.py")})

@app.route('/restart-ai', methods=['POST'])
def restart():
    return jsonify({"output": subprocess.getoutput("kubectl rollout restart deployment krrad-controller")})

@app.route('/heal', methods=['POST'])
def heal():
    subprocess.getoutput("kubectl delete pvc -l app.kubernetes.io/name=prometheus -n default --ignore-not-found")
    cmd = "kubectl get pods -A | awk 'NR>1 {split($3,a,\"/\"); if(a[1]!=a[2] || $4!=\"Running\") print $2 \" -n \" $1}' | xargs -L 1 kubectl delete pod --ignore-not-found"
    subprocess.getoutput(cmd)
    return jsonify({"output": "Cluster Auto-Heal Executed."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
