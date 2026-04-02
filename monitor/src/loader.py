from bcc import BPF
from flask import Flask, jsonify, request
import sys
import os
import socket, struct
import math

app = Flask(__name__)

device = os.environ.get("INTERFACE", "eth0")
xdp_mode = os.environ.get("XDP_MODE", "auto")
flags = (1 << 1) if xdp_mode == "skb" else 0

try:
    b = BPF(src_file="/app/src/xdp_counter.c")
    fn = b.load_func("xdp_prog", BPF.XDP)
    try: b.remove_xdp(device, flags)
    except: pass
    b.attach_xdp(device, fn, flags)
except Exception as e:
    sys.exit(1)

def ip_to_int(ip_str):
    return struct.unpack("!I", socket.inet_aton(ip_str))[0]

def calculate_shannon_entropy(ip_counts):
    """Calculates the Shannon Entropy of the source IP distribution."""
    if not ip_counts:
        return 0.0
    
    total_packets = sum(ip_counts.values())
    if total_packets == 0:
        return 0.0
        
    entropy = 0.0
    for count in ip_counts.values():
        probability = count / total_packets
        if probability > 0:
            entropy -= probability * math.log2(probability)
            
    return entropy

@app.route('/metrics', methods=['GET'])
def get_metrics():
    total_packets = total_bytes = 0
    details = {}
    for k, v in b["metrics_map"].items():
        proto = "TCP" if k.value == 6 else "UDP" if k.value == 17 else str(k.value)
        details[proto] = {"packets": v.packets, "bytes": v.bytes}
        total_packets += v.packets
        total_bytes += v.bytes

    max_packets = 0
    top_ip_str = None
    ip_counts = {}

    # Extract all IPs and calculate the top attacker
    for k, v in b["ip_tracker"].items():
        ip_str = socket.inet_ntoa(struct.pack("<I", k.value))
        ip_counts[ip_str] = v.value
        
        if v.value > max_packets:
            max_packets = v.value
            top_ip_str = ip_str

    ip_entropy = calculate_shannon_entropy(ip_counts)

    try: b["ip_tracker"].clear()
    except: pass

    return jsonify({
        "packets": total_packets, 
        "bytes": total_bytes, 
        "details": details, 
        "top_source_ip": top_ip_str,
        "ip_entropy": ip_entropy
    })

@app.route('/block', methods=['POST'])
def block_ip():
    ip = request.json.get('ip')
    if not ip: return jsonify({"error": "No IP"}), 400
    
    # Block Little Endian (Host Order)
    try:
        ip_le = struct.unpack("<I", socket.inet_aton(ip))[0]
        b["blacklist"][b["blacklist"].Key(ip_le)] = b["blacklist"].Leaf(1)
    except: pass

    # Block Big Endian (Network Order)
    try:
        ip_be = struct.unpack("!I", socket.inet_aton(ip))[0]
        b["blacklist"][b["blacklist"].Key(ip_be)] = b["blacklist"].Leaf(1)
    except: pass
    return jsonify({"status": "blocked", "ip": ip})

@app.route('/unblock', methods=['POST'])
def unblock_ip():
    ip = request.json.get('ip')
    if not ip: return jsonify({"error": "No IP"}), 400
    try: del b["blacklist"][b["blacklist"].Key(ip_to_int(ip))]
    except: pass
    return jsonify({"status": "unblocked", "ip": ip})

# Silently clear the eBPF map without restarting the pod
@app.route('/unblock_all', methods=['POST'])
def unblock_all():
    try:
        b["blacklist"].clear()
        return jsonify({"status": "success", "message": "eBPF Blacklist Flushed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)