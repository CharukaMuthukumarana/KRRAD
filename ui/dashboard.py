import streamlit as st
import os
import requests
import pandas as pd
import re
import time

st.set_page_config(
    page_title="KRRAD | AI Defense Hub",
    page_icon="assets/favicon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Background ── */
.stApp {
    background-color: #0b0f19;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #0f1623;
    border-right: 1px solid #1e2a3a;
}
[data-testid="stSidebar"] .stTextInput input {
    background-color: #1a2235;
    border: 1px solid #2a3a50;
    color: #e2e8f0;
    border-radius: 6px;
}
[data-testid="stSidebar"] .stTextInput input:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.25);
}

/* ── Page title ── */
.page-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: -0.5px;
    margin-bottom: 0.15rem;
}
.page-subtitle {
    font-size: 0.85rem;
    color: #64748b;
    margin-bottom: 1.5rem;
}

/* ── Section headers ── */
.section-header {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #475569;
    margin-bottom: 0.75rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #1e2a3a;
}

/* ── Cards ── */
.card {
    background-color: #111827;
    border: 1px solid #1e2a3a;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}

/* ── Status badge ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.badge-green  { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
.badge-red    { background: rgba(239,68,68,0.15);  color: #ef4444; border: 1px solid rgba(239,68,68,0.3);  }
.badge-yellow { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.badge-blue   { background: rgba(59,130,246,0.15); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3); }

/* ── Buttons ── */
.stButton > button {
    width: 100%;
    border-radius: 7px;
    height: 2.6rem;
    font-size: 0.82rem;
    font-weight: 500;
    letter-spacing: 0.02em;
    background-color: #1a2235;
    color: #cbd5e1;
    border: 1px solid #2a3a50;
    transition: all 0.18s ease;
}
.stButton > button:hover {
    background-color: #1e3a5f;
    border-color: #3b82f6;
    color: #f1f5f9;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59,130,246,0.2);
}
.stButton > button[kind="primary"] {
    background-color: #1d4ed8;
    border-color: #2563eb;
    color: #fff;
}
.stButton > button[kind="primary"]:hover {
    background-color: #2563eb;
    box-shadow: 0 4px 14px rgba(37,99,235,0.4);
}
.stButton > button[kind="secondary"] {
    background-color: #1f2937;
    border-color: #374151;
    color: #9ca3af;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background-color: #111827;
    border: 1px solid #1e2a3a;
    border-radius: 10px;
    padding: 1rem 1.25rem;
}
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.75rem !important; font-weight: 500 !important; text-transform: uppercase; letter-spacing: 0.06em; }
[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 1.6rem !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    border: 1px solid #1e2a3a;
    border-radius: 8px;
    overflow: hidden;
}

/* ── Divider ── */
hr { border-color: #1e2a3a !important; margin: 1.5rem 0 !important; }

/* ── Code block ── */
.stCode { border-radius: 8px !important; font-size: 0.78rem !important; }

/* ── Expander ── */
[data-testid="stExpander"] {
    background-color: #111827;
    border: 1px solid #1e2a3a;
    border-radius: 8px;
}

/* ── Checkbox ── */
.stCheckbox label { color: #94a3b8 !important; font-size: 0.85rem !important; }

/* ── Toast ── */
[data-testid="stToast"] { background-color: #1e2a3a !important; color: #e2e8f0 !important; border: 1px solid #2a3a50 !important; }

/* ── Selectbox / Number input ── */
.stSelectbox select, .stNumberInput input {
    background-color: #1a2235 !important;
    border: 1px solid #2a3a50 !important;
    color: #e2e8f0 !important;
    border-radius: 6px !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0b0f19; }
::-webkit-scrollbar-thumb { background: #1e2a3a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2a3a50; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "show_health" not in st.session_state:
    st.session_state.show_health = False

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="section-header">Connection</p>', unsafe_allow_html=True)
    krrad_vm_ip    = st.text_input("KRRAD Backend IP",  placeholder="35.xxx.xxx.xxx")
    attacker_vm_ip = st.text_input("Attacker VM IP",    placeholder="34.xxx.xxx.xxx")

    if krrad_vm_ip:
        st.markdown(
            '<span class="badge badge-green">&#10003; Connected</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"[Open Grafana Dashboard](http://{krrad_vm_ip}:3000)", unsafe_allow_html=False)
    else:
        st.markdown(
            '<span class="badge badge-yellow">&#9679; Not Connected</span>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown('<p class="section-header">Session</p>', unsafe_allow_html=True)
    if st.button("Refresh UI"):
        st.rerun()

# ── Helper ────────────────────────────────────────────────────────────────────
def fetch_from_vm(endpoint, method="GET", payload=None):
    if not krrad_vm_ip:
        return None
    url = f"http://{krrad_vm_ip}:8000/{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=5)
        else:
            r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception:
        return None

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown('<p class="page-title">KRRAD — AI Defense Hub</p>', unsafe_allow_html=True)
st.markdown('<p class="page-subtitle">Kubernetes-Native Autonomous DDoS Defense Framework</p>', unsafe_allow_html=True)

# ── Infrastructure ────────────────────────────────────────────────────────────
st.markdown('<p class="section-header">Infrastructure</p>', unsafe_allow_html=True)

col_h1, col_h2, col_spacer = st.columns([1, 1, 2])
with col_h1:
    if st.button("Toggle System Health"):
        st.session_state.show_health = not st.session_state.show_health
with col_h2:
    if st.button("Auto-Heal Cluster", type="secondary"):
        fetch_from_vm("heal", method="POST")
        st.toast("Auto-Heal initiated.")

if st.session_state.get("show_health", False):
    h_data = fetch_from_vm("health")
    if h_data and "pods" in h_data:
        df = pd.DataFrame(h_data["pods"])

        def color_health(val):
            if "Ready" in str(val):
                return "color: #10b981; font-weight: 600;"
            return "color: #ef4444; font-weight: 600;"

        st.dataframe(
            df.style.map(color_health, subset=["Health"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No health data available. Ensure the backend IP is set.")

st.divider()

# ── Attack Orchestration & Defense Operations ─────────────────────────────────
col_atk, col_def = st.columns(2, gap="large")

with col_atk:
    st.markdown('<p class="section-header">Attack Orchestration</p>', unsafe_allow_html=True)
    with st.container(border=True):
        a_c1, a_c2, a_c3 = st.columns(3)

        with a_c1:
            if st.button("SYN Flood (VM)"):
                try:
                    requests.post(
                        f"http://{attacker_vm_ip}:5000/launch",
                        json={"vector": "syn_flood", "target_ip": krrad_vm_ip, "target_port": "32028"},
                        timeout=5,
                    )
                    st.toast("SYN Flood launched.")
                except Exception:
                    st.error("Attacker VM is offline.")

        with a_c2:
            if st.button("Terraform Botnet"):
                fetch_from_vm("launch-terraform", method="POST")
                st.toast("Terraform Botnet launching...")

        with a_c3:
            if st.button("Stop All", type="secondary"):
                try:
                    requests.post(f"http://{attacker_vm_ip}:5000/stop", timeout=5)
                except Exception:
                    pass
                fetch_from_vm("stop-terraform", method="POST")
                st.toast("All attacks stopped.")

with col_def:
    st.markdown('<p class="section-header">Defense Operations</p>', unsafe_allow_html=True)
    with st.container(border=True):
        if st.button("Restart AI  —  Recalibrate"):
            fetch_from_vm("restart-ai", method="POST")
            st.toast("AI restarted. Commencing 30-second calibration...")

        d_c1, d_c2 = st.columns(2)
        with d_c1:
            if st.button("Reset System & Unblock IPs", type="primary"):
                fetch_from_vm("reset", method="POST")
                st.toast("System reset. All eBPF blocks flushed.")
                time.sleep(1)
                st.rerun()
        with d_c2:
            if st.button("Clear History"):
                fetch_from_vm("clear-history", method="POST")
                st.toast("Mitigation history cleared.")
                time.sleep(1)
                st.rerun()

# ── Mitigation History ────────────────────────────────────────────────────────
if krrad_vm_ip:
    st.divider()
    st.markdown('<p class="section-header">Mitigation History</p>', unsafe_allow_html=True)

    hist = fetch_from_vm("history")
    if hist:
        st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)

        with st.expander("Submit RLHF Feedback"):
            f_c1, f_c2, f_c3 = st.columns([1, 2, 1])
            with f_c1:
                tid = st.number_input("Action ID", min_value=1, step=1)
            with f_c2:
                fval = st.selectbox(
                    "Decision",
                    ["Good Decision", "False Positive", "Too Strict", "Too Lenient"],
                )
            with f_c3:
                st.write("")
                st.write("")
                if st.button("Submit Feedback"):
                    fetch_from_vm("submit-feedback", method="POST", payload={"id": tid, "value": fval})
                    st.toast("Feedback submitted.")
                    st.rerun()
    else:
        st.markdown(
            '<div class="card" style="text-align:center; color:#475569; font-size:0.85rem;">'
            'No mitigation events recorded yet.'
            '</div>',
            unsafe_allow_html=True,
        )

# ── Live Stream ───────────────────────────────────────────────────────────────
st.divider()
st.markdown('<p class="section-header">Live Traffic Stream</p>', unsafe_allow_html=True)

if st.checkbox("Enable Live Feed"):
    col_metrics, col_logs = st.columns([1, 2], gap="large")

    with col_metrics:
        p_pps = st.empty()
        p_rep = st.empty()

    with col_logs:
        p_log = st.empty()

    for _ in range(60):
        h_data = fetch_from_vm("health")
        if h_data and "pods" in h_data:
            df_h = pd.DataFrame(h_data["pods"])
            cnt = len(df_h[df_h["Pod"].str.contains("krrad-target", na=False)])
            p_rep.metric(
                "Target Replicas",
                f"{cnt} / 5",
                delta="Scaled Up" if cnt > 1 else None,
            )

        l_data = fetch_from_vm("logs")
        if l_data:
            logs = l_data.get("logs", "")
            pps  = re.findall(r"PPS: (\d+)", logs)
            p_pps.metric("Live Traffic", f"{pps[-1] if pps else '0'} PPS")
            p_log.code(logs, language="bash")

        time.sleep(2)
