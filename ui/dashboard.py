import streamlit as st
import os
import requests
import pandas as pd
import re
import time

st.set_page_config(page_title="KRRAD | AI Defense Hub", layout="wide", initial_sidebar_state="expanded")

if 'show_health' not in st.session_state:
    st.session_state.show_health = False

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #1f2937; color: white; border: 1px solid #374151; transition: 0.3s; }
    .stButton>button:hover { background-color: #ff4b4b; border: 1px solid #ff4b4b; transform: translateY(-2px); }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Cloud Configuration")
    krrad_vm_ip = st.text_input("🔑 KRRAD Backend IP", placeholder="35.xxx.xxx.xxx")
    attacker_vm_ip = st.text_input("📡 Attacker VM IP", placeholder="34.xxx.xxx.xxx")
    if krrad_vm_ip:
        st.success("Connected")
        st.markdown(f"📊 [**Grafana**](http://{krrad_vm_ip}:3000)")
    st.divider()
    if st.button("🔄 Reset UI"): st.rerun()

def fetch_from_vm(endpoint, method="GET", payload=None):
    if not krrad_vm_ip: return None
    url = f"http://{krrad_vm_ip}:8000/{endpoint}"
    try:
        if method == "GET": r = requests.get(url, timeout=5)
        else: r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except: return None

st.title("🛡️ KRRAD AI Defense Hub")

st.header("📋 Infrastructure")
col_h1, col_h2 = st.columns(2)
with col_h1:
    if st.button("🔍 Toggle Health Table"):
        st.session_state.show_health = not st.session_state.show_health
with col_h2:
    if st.button("🛠️ Auto-Heal Cluster", type="secondary"):
        fetch_from_vm("heal", method="POST")

if st.session_state.get('show_health', False):
    h_data = fetch_from_vm("health")
    if h_data and "pods" in h_data:
        df = pd.DataFrame(h_data["pods"])
        def color_health(val):
            return 'color: #00FF00' if 'Ready' in val else 'color: #FF0000'
        st.dataframe(df.style.map(color_health, subset=['Health']), use_container_width=True, hide_index=True)

st.divider()
col_atk, col_def = st.columns(2)
with col_atk:
    st.subheader("🚀 Attack Orchestration")
    with st.container(border=True):
        a_c1, a_c2 = st.columns(2)
        if a_c1.button("🌊 Targeted SYN (Block)"):
            try: requests.post(f"http://{attacker_vm_ip}:5000/launch", json={"vector": "syn_flood", "target_ip": krrad_vm_ip, "target_port": "32028"}, timeout=5)
            except: st.error("Attacker VM Offline")
        if a_c2.button("🛑 STOP ATTACK", type="secondary"):
            try: requests.post(f"http://{attacker_vm_ip}:5000/stop", timeout=5)
            except: pass

with col_def:
    st.subheader("🛡️ Defense Operations")
    with st.container(border=True):
        if st.button("🚨 EMERGENCY RESET", type="primary"):
            fetch_from_vm("reset", method="POST")
        if st.button("🧠 Restart AI"):
            fetch_from_vm("restart-ai", method="POST")

if krrad_vm_ip:
    st.divider()
    st.subheader("📜 Mitigation History")
    hist = fetch_from_vm("history")
    if hist:
        st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)

st.divider()
st.subheader("🧠 Live Stream")
if st.checkbox("Enable Feed"):
    c_m, c_l = st.columns([1, 2])
    with c_m:
        p_pps = st.empty()
        p_rep = st.empty()
    with c_l:
        p_log = st.empty()
    for _ in range(60):  
        h_data = fetch_from_vm("health")
        if h_data and "pods" in h_data:
            df_h = pd.DataFrame(h_data["pods"])
            cnt = len(df_h[df_h['Pod'].str.contains('krrad-target', na=False)])
            p_rep.metric("🎯 Target Replicas", f"{cnt} / 5", delta="SCALED UP" if cnt > 1 else None)
        l_data = fetch_from_vm("logs")
        if l_data:
            logs = l_data.get('logs', '')
            pps = re.findall(r"PPS: (\d+)", logs)
            p_pps.metric("📈 Traffic", f"{pps[-1] if pps else '0'} PPS")
            p_log.code(logs, language="bash")
        time.sleep(2)
