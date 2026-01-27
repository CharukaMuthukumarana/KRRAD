# monitor/src/loader.py
from bcc import BPF
from flask import Flask, jsonify, request
import sys
import threading
import time
import socket
import struct

# Initialize Flask
app = Flask(__name__)

# Load eBPF
device = "eth0"
print(f"Loading eBPF program on {device}...")
try:
    b = BPF(src_file="/app/src/xdp_counter.c")
    fn = b.load_func("xdp_prog", BPF.XDP)
    b.attach_xdp(device, fn, 0)
    print("eBPF Attached Successfully.")
except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    sys.exit(1)

# Helper: Convert IP string to int
def ip_to_int(ip_str):
    return struct.unpack("!I", socket.inet_aton(ip_str))[0]

@app.route('/metrics', methods=['GET'])
def get_metrics():
    # Read from kernel map
    data = {}
    for k, v in b["packet_counts"].items():
        proto = "TCP" if k.value == 6 else "UDP" if k.value == 17 else str(k.value)
        data[proto] = v.value
    return jsonify(data)

@app.route('/block', methods=['POST'])
def block_ip():
    # Add IP to blacklist map
    ip = request.json.get('ip')
    if not ip:
        return jsonify({"error": "No IP provided"}), 400
    
    ip_int = ip_to_int(ip)
    # 1 = Drop
    b["blacklist"][b["blacklist"].Key(ip_int)] = b["blacklist"].Leaf(1)
    print(f"BLOCKED IP: {ip}")
    return jsonify({"status": "blocked", "ip": ip})

@app.route('/unblock', methods=['POST'])
def unblock_ip():
    ip = request.json.get('ip')
    ip_int = ip_to_int(ip)
    try:
        del b["blacklist"][b["blacklist"].Key(ip_int)]
    except:
        pass
    return jsonify({"status": "unblocked", "ip": ip})

if __name__ == '__main__':
    # Run API on port 5000
    app.run(host='0.0.0.0', port=5000)