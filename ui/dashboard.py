import streamlit as st
import os
import requests
import pandas as pd
import re
import time

# Page Config
st.set_page_config(page_title="KRRAD | AI Defense Hub", layout="wide", initial_sidebar_state="expanded")

# --- Session State Initialization ---
if 'show_health' not in st.session_state:
    st.session_state.show_health = False

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

# --- UI Header ---
st.title("🛡️ KRRAD Distributed Defense Hub")
st.caption("Collaborative Research Node | Final Year Project - Charuka Muthukumarana")

# --- Section 1: Infrastructure Status ---
st.header("📋 Infrastructure Status")

col_health1, col_health2 = st.columns(2)
with col_health1:
    if st.button("🔍 Toggle System Health Table"):
        st.session_state.show_health = not st.session_state.show_health

with col_health2:
    if st.button("🛠️ Auto-Heal Cluster", type="secondary"):
        with st.spinner("Executing Deep Cluster Healing..."):
            res = fetch_from_vm("heal", method="POST")
            if res: 
                st.success(res.get('output'))

if st.session_state.get('show_health', False):
    with st.container(border=True):
        data = fetch_from_vm("health")
        if data and "pods" in data:
            df = pd.DataFrame(data["pods"])
            def color_health(val):
                if '✅' in val: return 'color: #00FF00'
                if '⚠️' in val: return 'color: #FFFF00'
                return 'color: #FF0000'
            st.dataframe(df.style.map(color_health, subset=['Health']), use_container_width=True, hide_index=True)
            if st.button("✖️ Close Table"):
                st.session_state.show_health = False
                st.rerun()

# --- Section 2: Command & Control ---
st.divider()
col_atk, col_def = st.columns(2)

with col_atk:
    st.subheader("🚀 Attack Orchestration")
    with st.container(border=True):
        a_col1, a_col2 = st.columns(2)
        if a_col1.button("🌊 Targeted SYN (Block)"):
            try: 
                requests.post(f"http://{attacker_vm_ip}:5000/launch", 
                              json={"vector": "syn_flood", "target_ip": krrad_vm_ip, "target_port": "32028"}, 
                              timeout=5)
                st.success("SYN Flood Started! System will Block IP.")
            except: 
                st.error("Failed to reach Attacker VM.")
            
        if a_col2.button("🐝 Flash Crowd (Scale)"):
            fetch_from_vm("simulate-swarm", method="POST")
            st.success("Trusted Swarm Started! Watch AI Scale Replicas...")
            
        if st.button("🛑 STOP ALL ATTACKS", type="secondary"):
            fetch_from_vm("stop-swarm", method="POST")
            try: 
                requests.post(f"http://{attacker_vm_ip}:5000/stop", timeout=5)
                st.info("Stop Command Sent. Cooling down...")
            except: 
                st.error("Failed to reach Attacker VM.")

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
            data = fetch_from_vm("restart-ai", method="POST")
            if data: 
                st.toast("AI Controller Restarting...")

# --- Section 3: History & Feedback ---
if krrad_vm_ip:
    st.divider()
    col_hist_title, col_hist_btn = st.columns([4, 1])
    with col_hist_title: 
        st.subheader("📜 RL Mitigation History & Human Feedback")
    with col_hist_btn:
        if st.button("🗑️ Clear History"):
            fetch_from_vm("clear-history", method="POST")
            st.rerun()

    history_data = fetch_from_vm("history")
    if history_data:
        df = pd.DataFrame(history_data)
        def color_feedback(val):
            return f"color: {'#00FF00' if val == 'Good Decision' else '#FF0000' if 'False' in val else '#FFFF00'}"
        st.dataframe(df.style.map(color_feedback, subset=['feedback']), use_container_width=True, hide_index=True)
	with st.expander("📝 Provide Feedback for RL Engine (RLHF)"):
            f_col1, f_col2, f_col3 = st.columns([1, 2, 1])
            target_id = f_col1.number_input("Action ID", min_value=1, step=1)
            feedback_val = f_col2.selectbox("Was this decision correct?", ["Good Decision", "False Positive / Overreaction"])
            if f_col3.button("Submit Feedback"):
                fetch_from_vm("submit-feedback", method="POST", payload={"id": target_id, "value": feedback_val})
                st.success(f"Feedback logged for Action {target_id}!")
                time.sleep(1)
                st.rerun()
    else:
        st.info("No mitigation actions recorded yet. Launch an attack to generate history.")

# --- Section 4: Live AI Intelligence Feed ---
st.divider()
st.subheader("🧠 Live AI Intelligence Feed")

if st.checkbox("Enable Real-time Stream"):
    # Create distinct columns to hold the live updating metrics
    col_metrics, col_logs = st.columns([1, 2])
    
    with col_metrics:
        pps_placeholder = st.empty()
        st.markdown("<br>", unsafe_allow_html=True)
        replica_placeholder = st.empty()
        
    with col_logs:
        log_placeholder = st.empty()
    
    for _ in range(60):  
        # 1. Update Replicas
        health_data = fetch_from_vm("health")
        if health_data and "pods" in health_data:
            df_health = pd.DataFrame(health_data["pods"])
            # Ensure the column matches your API response (usually 'Pod' or 'Pod Name')
            target_replicas = len(df_health[df_health['Pod'].str.contains('krrad-target', na=False)])
            
            with replica_placeholder.container():
                if target_replicas >= 5:
                    st.success(f"⚖️ **LIVE TARGET REPLICAS: {target_replicas} / 5 (SCALED UP)**")
                else:
                    st.info(f"⚖️ **LIVE TARGET REPLICAS: {target_replicas} / 5 (BASELINE)**")

        # 2. Update Logs
        data = fetch_from_vm("logs")
        if data:
            logs = data.get('logs', '')
            pps_match = re.findall(r"PPS: (\d+)", logs)
            current_pps = pps_match[-1] if pps_match else "0"
            
            with pps_placeholder.container():
                st.metric("📈 Detected Traffic", f"{current_pps} PPS")
                
            with log_placeholder.container():
                st.code(logs, language="bash")
        time.sleep(2)
else:
    st.info("Log streaming is paused.")
