"""HITL Formula Validation Dashboard — Orchestrator.

Usage:
    streamlit run scripts/hitl_dashboard.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

# ── Project path setup ───────────────────────────────────────────────
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from hitl.components.ai_analysis import render_ai_analysis
from hitl.components.audit_trail import render_audit_trail
from hitl.components.sidebar_queue import render_sidebar_queue
from hitl.components.verdict_panel import render_verdict_panel
from hitl.config import inject_css
from hitl.db_helpers import (
    _get_formula_health,
    _get_kpi_stats,
    run_async,
)
from hitl.pubsub import get_new_events, start_listener

# ── Page Config ──────────────────────────────────────────────────────
st.set_page_config(
    layout="wide",
    page_title="HITL Formula Dashboard",
    page_icon="🛡️",
    initial_sidebar_state="expanded",
)

inject_css()

# ── Redis Pub/Sub Listener ───────────────────────────────────────────
start_listener()
new_events = get_new_events()
for event in new_events:
    event_type = event.get("event_type")
    data = event.get("data", {})
    if event_type == "new_flagged_item":
        st.toast(
            f"🚨 YENİ KAYIT FLAGGED: {data.get('speaker_name', 'Bilinmiyor')} "
            f"({data.get('country', '?')}) | Risk: {data.get('ai_risk_score', 0)}/10",
            icon="🚨",
        )
    elif event_type == "verdict_submitted":
        st.toast(
            f"⚖️ YENİ KARAR SUBMITTED: Log #{data.get('log_id', '?')} | "
            f"Verdict: {data.get('verdict', '?')} by {data.get('reviewer_id', '?')}",
            icon="⚖️",
        )

# ── Session State Init ───────────────────────────────────────────────
if "current_log_id" not in st.session_state:
    st.session_state.current_log_id = None
if "reviewer_id" not in st.session_state:
    st.session_state.reviewer_id = "analyst@paxdata.local"
if "filter_formula" not in st.session_state:
    st.session_state.filter_formula = "Tümü"
if "filter_status" not in st.session_state:
    st.session_state.filter_status = "Bekleyen"
if "queue_data" not in st.session_state:
    st.session_state.queue_data = []

# ── Header ───────────────────────────────────────────────────────────
st.markdown("# 🛡️ HITL Formula Validation Dashboard")
st.markdown(
    "<p style='color:#94a3b8; margin-top:-10px;'>Human-in-the-Loop formül doğrulama & karar platformu</p>",
    unsafe_allow_html=True,
)

# Reviewer input in Sidebar
with st.sidebar:
    st.markdown("### 👤 Reviewer")
    reviewer_id = st.text_input(
        "Reviewer ID",
        value=st.session_state.reviewer_id,
        key="reviewer_input",
    )
    st.session_state.reviewer_id = reviewer_id

# ── KPI Strip (2.2.1) ───────────────────────────────────────────────
try:
    kpi_stats = run_async(_get_kpi_stats())
except Exception as e:
    kpi_stats = {
        "total_logs": 0,
        "total_pass": 0,
        "total_fail": 0,
        "pending_review": 0,
        "confirmed_fail": 0,
        "confirmed_pass": 0,
        "corrected": 0,
        "accuracy_percentage": 100.0,
    }
    st.warning(f"⚠️ KPI verisi alınamadı: {e}")

kpi_cols = st.columns(5)
with kpi_cols[0]:
    st.markdown(
        f"""<div class='kpi-card' style='border-left-color:#3b82f6;'>
        <div class='kpi-label'>Toplam Log</div>
        <div class='kpi-value'>{kpi_stats['total_logs']:,}</div>
        </div>""",
        unsafe_allow_html=True,
    )

with kpi_cols[1]:
    st.markdown(
        f"""<div class='kpi-card' style='border-left-color:#ef4444;'>
        <div class='kpi-label'>Toplam FAIL</div>
        <div class='kpi-value'>{kpi_stats['total_fail']:,}</div>
        </div>""",
        unsafe_allow_html=True,
    )

with kpi_cols[2]:
    pending = kpi_stats["pending_review"]
    pending_color = "#ef4444" if pending > 50 else "#f59e0b"
    st.markdown(
        f"""<div class='kpi-card' style='border-left-color:{pending_color};'>
        <div class='kpi-label'>İnceleme Bekleyen</div>
        <div class='kpi-value'>{pending:,}</div>
        </div>""",
        unsafe_allow_html=True,
    )

with kpi_cols[3]:
    st.markdown(
        f"""<div class='kpi-card' style='border-left-color:#10b981;'>
        <div class='kpi-label'>Doğruluk %</div>
        <div class='kpi-value'>{kpi_stats['accuracy_percentage']:.1f}%</div>
        </div>""",
        unsafe_allow_html=True,
    )

with kpi_cols[4]:
    corrected = kpi_stats["corrected"]
    st.markdown(
        f"""<div class='kpi-card' style='border-left-color:#7c3aed;'>
        <div class='kpi-label'>Düzeltilen</div>
        <div class='kpi-value'>{corrected:,}</div>
        </div>""",
        unsafe_allow_html=True,
    )

if pending > 50:
    st.warning(f"⚠️ Queue depth yüksek! {pending} kayıt bekliyor.")

# ── Formula Health Table (2.2.2) ─────────────────────────────────────
try:
    health_data = run_async(_get_formula_health())
except Exception:
    health_data = []

if health_data:
    with st.expander("📊 Formül Sağlık Tablosu", expanded=False):
        health_df = pd.DataFrame(health_data)
        health_df = health_df.rename(
            columns={
                "formula_name": "Formül",
                "total_fail": "Toplam FAIL",
                "false_positive_rate": "False Positive %",
                "correction_rate": "Düzeltme %",
                "confirmed_fail_count": "Onaylanan FAIL",
                "false_positive_count": "False Positive",
                "correction_count": "Düzeltme",
            }
        )
        if "False Positive %" in health_df.columns:
            health_df["False Positive %"] = (health_df["False Positive %"] * 100).map(
                lambda x: f"{x:.1f}%"
            )
            health_df["Düzeltme %"] = (health_df["Düzeltme %"] * 100).map(
                lambda x: f"{x:.1f}%"
            )
        st.dataframe(health_df, use_container_width=True, hide_index=True)

        for item in health_data:
            if item["false_positive_rate"] > 0.30:
                st.warning(
                    f"⚠️ **{item['formula_name']}** formülü "
                    f"%{item['false_positive_rate']*100:.1f} false positive üretiyor! "
                    f"Eşik ayarı gerekebilir."
                )

st.divider()

# ── Main Layout: Left Panel | Center | Right Panel ───────────────────
left_col, center_col, right_col = st.columns([1, 2.5, 1])

# Left column: sidebar filters and queue list
with left_col:
    queue_data, selected_item = render_sidebar_queue()

# Center column: selected sentence details and verdict panel
with center_col:
    render_verdict_panel(selected_item, queue_data)

# Right column: AI metrics and speaker profiles
with right_col:
    render_ai_analysis(selected_item, queue_data)

# Bottom section: audit logs expander
st.divider()
render_audit_trail()

st.markdown(
    "<div style='text-align:center; color:#475569; padding:20px; font-size:0.8rem;'>"
    "HITL Formula Validation Dashboard v3.0 — PAXDATA"
    "</div>",
    unsafe_allow_html=True,
)
