import streamlit as st
import os
import requests
import pandas as pd
import re
import time

# Page Config
st.set_page_config(page_title="KRRAD | AI Defense Hub", layout="wide", initial_sidebar_state="expanded")

# --- Enhanced Styling ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #1f2937; color: white; border: 1px solid #374151; transition: 0.3s; }
    .stButton>button:hover { background-color: #ff4b4b; border: 1px solid #ff4b4b; transform: translateY(-2px); }
    </style>
    """, unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Cloud Configuration")
    krrad_vm_ip = st.text_input("🔑 KRRAD Backend IP", placeholder="35.xxx.xxx.xxx")
    attacker_vm_ip = st.text_input("📡 Attacker VM IP", placeholder="34.xxx.xxx.xxx")
    
    if krrad_vm_ip:
        st.success("Connected to Backend")
        st.markdown(f"📊 [**Open Grafana**](http://{krrad_vm_ip}:3000)")
    else:
        st.warning("Please enter VM IP to fetch data")
    
    st.divider()
    if st.button("🔄 Hard Reset UI"):
        st.rerun()

# --- API Helper Functions ---
def fetch_from_vm(endpoint, method="GET", payload=None):
    if not krrad_vm_ip: return None
    url = f"http://{krrad_vm_ip}:8000/{endpoint}"
    try:
        if method == "GET": 
            r = requests.get(url, timeout=5)
        else: 
            r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except: 
        return None

def send_remote_attack(vector, target_ip):
    if not attacker_vm_ip: return False
    try:
        url = f"http://{attacker_vm_ip}:5000/launch"
        payload = {"vector": vector, "target_ip": target_ip, "target_port": "32028"}
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code == 200
    except: 
        return False

# --- UI Header ---
st.title("🛡️ KRRAD Distributed Defense Hub")
st.caption(f"Collaborative Research Node | Final Year Project - Charuka Muthukumarana")

# --- Section 1: Infrastructure Status ---
st.header("📋 Infrastructure Status")

if st.button("🔍 Refresh System Health"):
    data = fetch_from_vm("health")
    if data:
        st.subheader("Live Pod Status")
        # Ensure we use 'output' key as defined in management_api.py
        st.text(data.get('output', 'No data returned.'))
    else:
        st.error("Backend unreachable. Ensure Port 8000 is open on GCP Firewall.")

# --- Section 2: Command & Control ---
st.divider()
col_atk, col_def = st.columns(2)

with col_atk:
    st.subheader("🚀 Attack Orchestration")
    with st.container(border=True):
        a_col1, a_col2 = st.columns(2)
        if a_col1.button("🌊 SYN Flood"):
            if send_remote_attack("syn_flood", krrad_vm_ip): st.success("SYN Flood Started")
            else: st.error("Attack failed.")
            
        if a_col2.button("🚀 UDP Flood"):
            if send_remote_attack("udp_flood", krrad_vm_ip): st.success("UDP Flood Started")
            else: st.error("Attack failed.")
            
        if a_col1.button("🔥 HTTP Flood"):
            if send_remote_attack("http_flood", krrad_vm_ip): st.success("HTTP Flood Started")
            else: st.error("Attack failed.")
            
        if a_col2.button("🛑 STOP ATTACKS", type="secondary"):
            try:
                requests.post(f"http://{attacker_vm_ip}:5000/stop", timeout=5)
                st.info("Stop Command Sent")
            except: 
                st.error("Attacker Offline")

with col_def:
    st.subheader("🛡️ Defense Operations")
    with st.container(border=True):
        if st.button("🚨 EMERGENCY RESET", type="primary"):
            with st.status("Requesting Remote Reset...", expanded=True) as status:
                data = fetch_from_vm("reset", method="POST")
                if data:
                    st.code(data.get('output', 'Reset executed.'))
                    status.update(label="System Baseline Restored!", state="complete")
                else:
                    st.error("Failed to reach Backend API.")
        
        if st.button("🧠 Restart RL Agent"):
            # FIXED: Endpoint changed to match management_api.py route
            data = fetch_from_vm("restart-ai", method="POST")
            if data:
                st.toast("AI Controller Restarting...")
            else:
                st.error("Failed to reach Backend API.")

# --- Section 3: Real-Time Intelligence ---
st.divider()
st.subheader("🧠 Live AI Intelligence Feed")

if st.checkbox("Enable Real-time Stream"):
    log_placeholder = st.empty()
    for _ in range(30):  # Stream for about a minute
        data = fetch_from_vm("logs")
        if data:
            # FIXED: Key changed to 'logs' to match management_api.py
            logs = data.get('logs', '')
            pps_match = re.findall(r"PPS: (\d+)", logs)
            current_pps = pps_match[-1] if pps_match else "0"
            
            with log_placeholder.container():
                st.metric("Detected Traffic (PPS)", f"{current_pps} pkts/sec")
                st.code(logs, language="bash")
        else:
            st.warning("Waiting for data from API...")
        time.sleep(2)
else:
    st.info("Log streaming is paused.")
