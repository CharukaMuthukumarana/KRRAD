from flask import Flask, jsonify, request
import subprocess
import re
import datetime

app = Flask(__name__)

# In-memory storage for the RLHF Demo
mitigation_history = []
seen_logs = set()

@app.route('/health', methods=['GET'])
def health():
    cmd = "kubectl get pods -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,READY:.status.containerStatuses[*].ready,STATUS:.status.phase"
    return jsonify({"output": subprocess.getoutput(cmd)})

@app.route('/logs', methods=['GET'])
def logs():
    return jsonify({"logs": subprocess.getoutput("kubectl logs --tail=20 -l app=krrad-controller")})

@app.route('/history', methods=['GET'])
def get_history():
    global mitigation_history, seen_logs
    # Fetch a larger chunk of logs to parse history
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
    
    # Return reversed list so newest is on top
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

@app.route('/reset', methods=['POST'])
def reset():
    global mitigation_history, seen_logs
    mitigation_history.clear()
    seen_logs.clear()
    return jsonify({"output": subprocess.getoutput("python3 /home/charuka2002buss/KRRAD/demo/reset.py")})

@app.route('/restart-ai', methods=['POST'])
def restart():
    return jsonify({"output": subprocess.getoutput("kubectl rollout restart deployment krrad-controller")})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
