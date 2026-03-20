from flask import Flask, jsonify
import subprocess
import os

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    cmd = "kubectl get pods -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,READY:.status.containerStatuses[*].ready,STATUS:.status.phase"
    output = subprocess.getoutput(cmd)
    return jsonify({"output": output})

@app.route('/logs', methods=['GET'])
def logs():
    # Fetching logs from the controller
    output = subprocess.getoutput("kubectl logs --tail=20 -l app=krrad-controller")
    return jsonify({"logs": output})

@app.route('/reset', methods=['POST'])
def reset():
    # Triggering your existing reset script
    output = subprocess.getoutput("python3 /home/charuka2002buss/KRRAD/demo/reset.py")
    return jsonify({"output": output})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
