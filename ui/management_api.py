from flask import Flask, jsonify, request
import subprocess
import os

app = Flask(__name__)

# Security: In a real app, you'd add an API Key check here
@app.route('/health', methods=['GET'])
def health():
    cmd = "kubectl get pods -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,READY:.status.containerStatuses[*].ready,STATUS:.status.phase"
    output = subprocess.getoutput(cmd)
    return jsonify({"output": output})

@app.route('/logs', methods=['GET'])
def logs():
    output = subprocess.getoutput("kubectl logs --tail=20 -l app=krrad-controller")
    return jsonify({"logs": output})

@app.route('/reset', methods=['POST'])
def reset():
    output = subprocess.getoutput("python3 /home/charuka2002buss/KRRAD/demo/reset.py")
    return jsonify({"output": output})

@app.route('/restart-ai', methods=['POST'])
def restart_ai():
    output = subprocess.getoutput("kubectl rollout restart deployment krrad-controller")
    return jsonify({"output": output})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
