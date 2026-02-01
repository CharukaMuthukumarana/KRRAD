from bcc import BPF
from flask import Flask, jsonify, request
import sys
import os

app = Flask(__name__)

# Configuration
device = os.environ.get("INTERFACE", "eth0")
xdp_mode = os.environ.get("XDP_MODE", "auto")

print(f"KRRAD Sensor Initializing on {device} (Mode: {xdp_mode})")

flags = 0
if xdp_mode == "skb":
    print("Forcing Generic XDP Mode (SKB)")
    flags = (1 << 1)

# Load eBPF Program
try:
    b = BPF(src_file="/app/src/xdp_counter.c")
    fn = b.load_func("xdp_prog", BPF.XDP)
    
    # Detach any existing XDP programs
    try:
        b.remove_xdp(device, flags)
    except Exception:
        pass
    
    b.attach_xdp(device, fn, flags)
    print("eBPF Program Attached Successfully.")
except Exception as e:
    print(f"Critical Error: {e}")
    sys.exit(1)

def ip_to_int(ip_str):
    import socket, struct
    return struct.unpack("!I", socket.inet_aton(ip_str))[0]

@app.route('/metrics', methods=['GET'])
def get_metrics():
    total_packets = 0
    total_bytes = 0
    details = {}
    
    for k, v in b["metrics_map"].items():
        proto = "TCP" if k.value == 6 else "UDP" if k.value == 17 else str(k.value)
        details[proto] = {
            "packets": v.packets,
            "bytes": v.bytes
        }
        total_packets += v.packets
        total_bytes += v.bytes

    return jsonify({
        "packets": total_packets,
        "bytes": total_bytes,
        "details": details
    })

@app.route('/block', methods=['POST'])
def block_ip():
    ip = request.json.get('ip')
    if not ip: return jsonify({"error": "No IP"}), 400
    
    ip_int = ip_to_int(ip)
    b["blacklist"][b["blacklist"].Key(ip_int)] = b["blacklist"].Leaf(1)
    print(f"Blocked IP: {ip}")
    return jsonify({"status": "blocked", "ip": ip})

@app.route('/unblock', methods=['POST'])
def unblock_ip():
    ip = request.json.get('ip')
    if not ip: return jsonify({"error": "No IP"}), 400
    
    try:
        del b["blacklist"][b["blacklist"].Key(ip_to_int(ip))]
    except Exception:
        pass
    return jsonify({"status": "unblocked", "ip": ip})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)