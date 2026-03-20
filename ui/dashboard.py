import streamlit as st
import os
import subprocess
import time

st.set_page_config(page_title="KRRAD | AI Defense Hub", layout="wide", initial_sidebar_state="expanded")

# --- Styling ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #262730; color: white; }
    .stButton>button:hover { background-color: #ff4b4b; border: 1px solid #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ KRRAD: Kubernetes RL-Based DDoS Defense")
st.caption("Final Year Project - Charuka Muthukumarana | Supervisor: Mr. Lakshan Costa")

# --- Sidebar ---
with st.sidebar:
    st.header("🔗 External Links")
    vm_ip = os.popen('curl -s ifconfig.me').read().strip()
    st.markdown(f"📊 [**Open Grafana Dashboard**](http://{vm_ip}:3000)")
    st.divider()
    st.info("System Mode: **Production (Cloud)**")

# --- Function to run commands and capture output ---
def run_action(cmd):
    try:
        # This captures the actual terminal output to show in the UI
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        return True, result
    except subprocess.CalledProcessError as e:
        return False, e.output

# --- Section 1: System Health ---
st.header("📋 System Health")
if st.button("🔍 Refresh Pod Status"):
    pod_data = os.popen("kubectl get pods -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,STATUS:.status.phase").read()
    st.text(pod_data)

# --- Section 2: Attack & Defense ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("🚀 Attack Simulation")
    if st.button("📡 Deploy Internal Botnet"):
        # Using absolute path for reliability
        success, out = run_action("kubectl apply -f /home/charuka2002buss/KRRAD/demo/attacker.yaml")
        if success: st.success("Botnet pods creating...")
        else: st.error(f"Failed: {out}")
    
    if st.button("🔥 Run High-Scale Flood"):
        st.warning("Initiating attack sequence...")
        subprocess.Popen(["python3", "/home/charuka2002buss/KRRAD/demo/attack_scale.py"])
        st.success("Attack scale script running in background.")

with col2:
    st.subheader("🛡️ Defense Operations")
    # This button now calls the WORKING reset.py script
    if st.button("🛑 EMERGENCY: UNBLOCK & RESET"):
        with st.spinner("Executing Reset Protocol..."):
            success, out = run_action("python3 /home/charuka2002buss/KRRAD/demo/reset.py")
            if success:
                st.success("System Reset Complete!")
                st.code(out) # Shows the actual output from reset.py
            else:
                st.error("Reset Failed!")
                st.code(out)

    if st.button("🧠 Restart AI Controller"):
        success, out = run_action("kubectl rollout restart deployment krrad-controller")
        if success: st.info("Controller memory cleared and restarted.")
        else: st.error(out)

# --- Section 3: Live AI Insights ---
st.divider()
st.subheader("🧠 AI Controller Live Feed")
if st.checkbox("Show Real-time Logs"):
    log_output = os.popen("kubectl logs --tail=15 -l app=krrad-controller").read()
    st.code(log_output, language="bash")
