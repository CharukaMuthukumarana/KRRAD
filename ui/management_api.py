from flask import Flask, jsonify, request
import subprocess
import re
import datetime

app = Flask(__name__)
mitigation_history = []

@app.route('/health', methods=['GET'])
def health():
    output = subprocess.getoutput("kubectl get pods -A")
    pods = []
    for line in output.strip().split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 6:
            ns, name, ready, status = parts[0], parts[1], parts[2], parts[3]
            health_stat = f"❌ {status}" if status != "Running" else ("✅ Ready" if ready.split('/')[0] == ready.split('/')[1] else "⚠️ Partial/Crashing")
            pods.append({"Namespace": ns, "Pod": name, "Ready": ready, "Status": status, "Health": health_stat})
    return jsonify({"pods": pods, "raw": output})

@app.route('/logs', methods=['GET'])
def logs():
    return jsonify({"logs": subprocess.getoutput("kubectl logs --tail=20 -l app=krrad-controller")})

@app.route('/history', methods=['GET'])
def get_history():
    return jsonify(mitigation_history[::-1])

@app.route('/report-action', methods=['POST'])
def report_action():
    data = request.json
    mitigation_history.append({
        "id": len(mitigation_history) + 1,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        "action": data.get("action"),
        "pps": data.get("pps"),
        "feedback": "Awaiting Admin Review"
    })
    return jsonify({"status": "logged"})

@app.route('/submit-feedback', methods=['POST'])
def feedback():
    data = request.json
    for item in mitigation_history:
        if item["id"] == data.get("id"):
            item["feedback"] = data.get("value")
            break
    return jsonify({"status": "updated"})

@app.route('/clear-history', methods=['POST'])
def clear_history():
    mitigation_history.clear()
    return jsonify({"status": "cleared"})

@app.route('/simulate-swarm', methods=['POST'])
def simulate_swarm():
    # 🔥 VIVA FIX: Strict 127.0.0.1 traffic to guarantee Scale Up logic
    cmd = "docker run --rm -d --name swarm_flood --net=host alpine sh -c 'apk add --no-cache hping3 && hping3 -S --flood -p 32028 127.0.0.1'"
    subprocess.Popen(cmd, shell=True)
    return jsonify({"status": "Swarm simulated"})

@app.route('/stop-swarm', methods=['POST'])
def stop_swarm():
    subprocess.getoutput("docker rm -f swarm_flood")
    return jsonify({"status": "stopped"})

@app.route('/reset', methods=['POST'])
def reset():
    mitigation_history.clear()
    return jsonify({"output": subprocess.getoutput("python3 /home/charuka2002buss/KRRAD/demo/reset.py")})

@app.route('/restart-ai', methods=['POST'])
def restart():
    return jsonify({"output": subprocess.getoutput("kubectl rollout restart deployment krrad-controller")})

@app.route('/heal', methods=['POST'])
def heal():
    subprocess.getoutput("kubectl delete pvc -l app.kubernetes.io/name=prometheus -n default --ignore-not-found")
    subprocess.getoutput("kubectl get pods -A | awk 'NR>1 {split($3,a,\"/\"); if(a[1]!=a[2] || $4!=\"Running\") print $2 \" -n \" $1}' | xargs -L 1 kubectl delete pod --ignore-not-found")
    return jsonify({"output": "Cluster Auto-Heal Executed."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
