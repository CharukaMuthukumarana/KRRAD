import streamlit as st
import os
import subprocess
import requests
import time
import pandas as pd
import re

# Page Config
st.set_page_config(page_title="KRRAD | AI Defense Hub", layout="wide", initial_sidebar_state="expanded")

# --- Enhanced Styling ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #1f2937; color: white; border: 1px solid #374151; transition: 0.3s; }
    .stButton>button:hover { background-color: #ff4b4b; border: 1px solid #ff4b4b; transform: translateY(-2px); }
    .status-card { padding: 20px; border-radius: 10px; background-color: #111827; border-left: 5px solid #ff4b4b; margin-bottom: 10px; }
    .log-container { background-color: #000000; color: #00ff00; padding: 15px; border-radius: 5px; font-family: 'Courier New', Courier, monospace; height: 300px; overflow-y: auto; }
    </style>
    """, unsafe_allow_html=True)

# --- Session State Initialization ---
if 'show_pods' not in st.session_state: st.session_state.show_pods = False
if 'log_active' not in st.session_state: st.session_state.log_active = False

# --- Helper Functions ---
def get_ip():
    return os.popen('curl -s ifconfig.me').read().strip()

def get_detailed_pods():
    # Fetch Namespace, Name, Ready status, and Phase
    cmd = "kubectl get pods -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,READY:.status.containerStatuses[*].ready,STATUS:.status.phase"
    lines = os.popen(cmd).read().strip().split('\n')[1:]
    data = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 4:
            # Logic: A pod is ONLY "Healthy" if ALL containers are True
            ready_list = parts[2].split(',')
            is_fully_ready = all(r.lower() == 'true' for r in ready_list)
            status_text = "✅ Ready" if (is_fully_ready and parts[3] == "Running") else "⚠️ Partial/Starting"
            if parts[3] != "Running": status_text = f"❌ {parts[3]}"
            
            data.append({"Namespace": parts[0], "Pod Name": parts[1], "Health": status_text, "Status": parts[3]})
    return pd.DataFrame(data)

def send_remote_attack(vector, attacker_ip, target_ip):
    try:
        url = f"http://{attacker_ip}:5000/launch"
        payload = {"vector": vector, "target_ip": target_ip, "target_port": "32028"}
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code == 200
    except: return False

# --- UI Header ---
st.title("🛡️ KRRAD: AI-Driven DDoS Defense")
st.caption(f"Collaborative Research Node | Logged in as: {os.getlogin()}")

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Control Plane")
    attacker_ip = st.text_input("📡 Attacker VM IP", placeholder="Paste IP here...")
    vm_ip = get_ip()
    
    st.divider()
    st.metric(label="System Status", value="PROTECTED", delta="AI Active")
    st.markdown(f"📊 [**Open Grafana**](http://{vm_ip}:3000)")
    
    if st.button("🔄 Hard Reset UI"):
        st.rerun()

# --- Section 1: Dynamic System Health ---
st.header("📋 Infrastructure Status")
col_h1, col_h2 = st.columns([1, 4])

with col_h1:
    # Toggle functionality using Session State
    if st.button("🔍 Toggle Pod View"):
        st.session_state.show_pods = not st.session_state.show_pods

if st.session_state.show_pods:
    df = get_detailed_pods()
    # Highlighting specific KRRAD components
    st.dataframe(df, use_container_width=True, hide_index=True)
    if st.button("✖️ Close Pod View"):
        st.session_state.show_pods = False
        st.rerun()

# --- Section 2: Command & Control ---
st.divider()
col_atk, col_def = st.columns(2)

with col_atk:
    st.subheader("🚀 Attack Orchestration")
    with st.container(border=True):
        a_col1, a_col2 = st.columns(2)
        if a_col1.button("🌊 SYN Flood"):
            if send_remote_attack("syn_flood", attacker_ip, vm_ip): st.success("SYN Flood Started")
        if a_col2.button("🚀 UDP Flood"):
            if send_remote_attack("udp_flood", attacker_ip, vm_ip): st.success("UDP Flood Started")
        if a_col1.button("🔥 HTTP Flood"):
            if send_remote_attack("http_flood", attacker_ip, vm_ip): st.success("HTTP Flood Started")
        if a_col2.button("🛑 STOP ATTACKS", type="secondary"):
            try:
                requests.post(f"http://{attacker_ip}:5000/stop", timeout=5)
                st.info("Stop Command Sent")
            except: st.error("Attacker Offline")

with col_def:
    st.subheader("🛡️ Defense Operations")
    with st.container(border=True):
        if st.button("🚨 EMERGENCY RESET", type="primary"):
            with st.status("Executing Deep Clean...", expanded=True) as status:
                out = subprocess.getoutput("python3 /home/charuka2002buss/KRRAD/demo/reset.py")
                st.code(out)
                status.update(label="System Baseline Restored!", state="complete")
        
        if st.button("🧠 Restart RL Agent"):
            os.system("kubectl rollout restart deployment krrad-controller")
            st.toast("AI Controller Restarting...")

# --- Section 3: Real-Time Intelligence ---
st.divider()
st.subheader("🧠 Live AI Intelligence Feed")

log_toggle = st.toggle("Enable Real-time Stream", value=st.session_state.log_active)
st.session_state.log_active = log_toggle

if st.session_state.log_active:
    log_placeholder = st.empty()
    # Display logic for real-time feel
    for _ in range(20): # Loop to simulate streaming
        logs = os.popen("kubectl logs --tail=15 -l app=krrad-controller").read()
        
        # Extra Feature: Extract PPS from logs for a live metric
        pps_match = re.findall(r"PPS: (\d+)", logs)
        current_pps = pps_match[-1] if pps_match else "0"
        
        with log_placeholder.container():
            st.metric("Detected Traffic (PPS)", f"{current_pps} pkts/sec")
            st.code(logs, language="bash")
        time.sleep(2)
        if not st.session_state.log_active: break
else:
    st.info("Log streaming is paused. Enable the toggle above to start.")

