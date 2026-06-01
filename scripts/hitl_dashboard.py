"""HITL Formula Validation Dashboard — Streamlit MVP.

Usage:
    streamlit run scripts/hitl_dashboard.py

Requires:
    pip install streamlit pandas plotly
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# ── Project path setup ───────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

load_dotenv()

from bb_paxdata.infrastructure.db.repositories.formula_validation import (  # noqa: E402
    FormulaValidationRepository,
)

# ── Constants ────────────────────────────────────────────────────────

FORMULA_ICONS = {
    "hedging_score": "🛡️",
    "risk_score": "🔥",
    "emotion_category_alignment": "🎭",
    "sbi_score": "📊",
    "dki_score": "🤝",
    "vader_compound": "📈",
    "negation_aware_diplo": "🔄",
    "politeness_ratio": "🎩",
    "segment_data_quality": "📋",
}

VERDICT_COLORS = {
    "CONFIRMED_PASS": "#10B981",
    "CONFIRMED_FAIL": "#7F1D1D",
    "CORRECTED": "#7C3AED",
    None: "#F59E0B",  # Pending
}

STATUS_COLORS = {
    "PASS": "#10B981",
    "FAIL": "#EF4444",
}


# ── CSS Styling ──────────────────────────────────────────────────────


def inject_css():
    """Inject custom CSS for the dashboard."""
    st.markdown(
        """
        <style>
        /* ─── Global ─── */
        .stApp {
            background-color: #0f172a;
        }
        section[data-testid="stSidebar"] {
            background-color: #1e293b;
        }
        h1, h2, h3 { color: #f1f5f9 !important; }

        /* ─── KPI Card ─── */
        .kpi-card {
            background: linear-gradient(135deg, #1e293b, #334155);
            border-radius: 12px;
            padding: 16px 20px;
            border-left: 4px solid;
            margin-bottom: 8px;
        }
        .kpi-card .kpi-label {
            color: #94a3b8;
            font-size: 0.85rem;
            margin-bottom: 4px;
        }
        .kpi-card .kpi-value {
            color: #f1f5f9;
            font-size: 1.8rem;
            font-weight: 700;
        }

        /* ─── Queue Item ─── */
        .queue-item {
            background: #1e293b;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 6px;
            border-left: 3px solid;
            cursor: pointer;
            transition: all 0.2s;
        }
        .queue-item:hover {
            background: #334155;
            transform: translateX(4px);
        }
        .queue-item.selected {
            background: #334155;
            border-left-color: #3b82f6 !important;
        }
        .queue-item .formula-name {
            color: #e2e8f0;
            font-weight: 600;
            font-size: 0.95rem;
        }
        .queue-item .sentence-preview {
            color: #94a3b8;
            font-size: 0.8rem;
            margin-top: 4px;
        }

        /* ─── Triplet Card ─── */
        .triplet-container {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
        }
        .triplet-prev, .triplet-next {
            color: #64748b;
            font-style: italic;
            padding: 8px 12px;
            border-left: 2px solid #475569;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }
        .triplet-current {
            color: #f1f5f9;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 1.05rem;
            font-weight: 500;
            margin: 8px 0;
        }
        .triplet-current.fail {
            background: rgba(239, 68, 68, 0.1);
            border-left: 4px solid #ef4444;
        }
        .triplet-current.corrected {
            background: rgba(124, 58, 237, 0.1);
            border-left: 4px solid #7c3aed;
        }
        .triplet-current.pass {
            background: rgba(16, 185, 129, 0.1);
            border-left: 4px solid #10b981;
        }

        /* ─── Formula Breakdown ─── */
        .formula-card {
            background: #1e293b;
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 12px;
        }
        .formula-card .formula-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }
        .formula-card .formula-icon {
            font-size: 1.4rem;
        }
        .formula-card .formula-title {
            color: #e2e8f0;
            font-weight: 700;
            font-size: 1.1rem;
        }

        /* ─── Badge ─── */
        .badge {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .badge-fail { background: #ef4444; color: #fff; }
        .badge-pass { background: #10b981; color: #fff; }
        .badge-pending { background: #f59e0b; color: #1e293b; }
        .badge-corrected { background: #7c3aed; color: #fff; }
        .badge-confirmed-fail { background: #7f1d1d; color: #fca5a5; }
        .badge-confirmed-pass { background: #065f46; color: #6ee7b7; }

        /* ─── Audit Trail ─── */
        .audit-entry {
            background: #1e293b;
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .audit-entry .audit-time {
            color: #64748b;
            font-size: 0.8rem;
            min-width: 80px;
        }
        .audit-entry .audit-action {
            color: #e2e8f0;
            font-size: 0.85rem;
        }

        /* ─── AI Metric ─── */
        .ai-metric {
            background: #1e293b;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
        }
        .ai-metric .metric-label {
            color: #94a3b8;
            font-size: 0.8rem;
        }
        .ai-metric .metric-value {
            color: #f1f5f9;
            font-size: 1.3rem;
            font-weight: 700;
        }

        /* ─── Verdict Buttons ─── */
        div[data-testid="stHorizontalBlock"] > div > div > button {
            border-radius: 10px;
            font-weight: 600;
            padding: 8px 16px;
            transition: all 0.2s;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Database Connection Helper ───────────────────────────────────────


def get_database_url() -> str:
    """Build async database URL from .env."""
    url = os.getenv("DATABASE_URL", "sqlite:///./data/paxdata.db")
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    elif url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@st.cache_resource
def get_engine():
    """Create a cached async engine."""
    return create_async_engine(get_database_url(), echo=False)


def run_async(coro):
    """Run an async coroutine in a sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _get_kpi_stats() -> dict[str, Any]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_kpi_stats()


async def _get_formula_health() -> list[dict[str, Any]]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_formula_health()


async def _get_fail_queue(
    formula_name: str | None = None,
    panel_id: str | None = None,
    status_filter: str = "unreviewed",
    limit: int = 50,
) -> list[dict[str, Any]]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_fail_queue_with_context(
            formula_name=formula_name,
            panel_id=panel_id,
            status_filter=status_filter,
            limit=limit,
        )


async def _get_triplet_context(sent_id: str) -> dict[str, str | None]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_triplet_context(sent_id)


async def _get_similar_cases(
    sent_id: str, formula_name: str, country: str | None = None
) -> list[dict[str, Any]]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_similar_cases(
            sent_id=sent_id, formula_name=formula_name, country=country
        )


async def _submit_verdict(
    log_id: int,
    verdict: str,
    corrected_value: float | None,
    note: str | None,
    confidence: str | None,
    justification: str | None,
    reviewer_id: str,
) -> dict[str, Any]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        result = await repo.submit_verdict_atomic(
            log_id=log_id,
            verdict=verdict,
            corrected_value=corrected_value,
            note=note,
            confidence=confidence,
            justification=justification,
            reviewer_id=reviewer_id,
        )
        await session.commit()
        return result


async def _get_audit_trail(limit: int = 10) -> list[dict[str, Any]]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_audit_trail(limit=limit)


async def _start_review(log_id: int, reviewer_id: str):
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        result = await repo.start_review(log_id, reviewer_id)
        await session.commit()
        return result


# ── Page Config ──────────────────────────────────────────────────────

st.set_page_config(
    layout="wide",
    page_title="HITL Formula Dashboard",
    page_icon="🛡️",
    initial_sidebar_state="expanded",
)

inject_css()

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

# Reviewer giriş
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
    st.warning(f"⚠️ Queue depth yüksek! {pending} item bekliyor.")

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
        # Format percentages
        if "False Positive %" in health_df.columns:
            health_df["False Positive %"] = (health_df["False Positive %"] * 100).map(
                lambda x: f"{x:.1f}%"
            )
            health_df["Düzeltme %"] = (health_df["Düzeltme %"] * 100).map(
                lambda x: f"{x:.1f}%"
            )
        st.dataframe(health_df, use_container_width=True, hide_index=True)

        # Alert for high false positive rates
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

# ═══════════════════════════════════════════════════════════════════
# LEFT PANEL: Filters + Queue (2.3.1, 2.3.2, 2.3.3)
# ═══════════════════════════════════════════════════════════════════

with left_col:
    st.markdown("### 🔍 Filtreler")

    # Formula filter
    formula_names = ["Tümü", *FORMULA_ICONS.keys()]
    filter_formula = st.selectbox(
        "Formül",
        formula_names,
        index=0,
        key="formula_filter_select",
    )

    # Status filter
    status_options = {"Bekleyen": "unreviewed", "İncelenen": "reviewed", "Tümü": "all"}
    filter_status = st.radio(
        "Durum",
        list(status_options.keys()),
        horizontal=True,
        key="status_filter_radio",
    )

    st.divider()
    st.markdown("### 📋 FAIL Queue")

    # Fetch queue data
    try:
        queue_data = run_async(
            _get_fail_queue(
                formula_name=filter_formula if filter_formula != "Tümü" else None,
                status_filter=status_options[filter_status],
                limit=50,
            )
        )
        st.session_state.queue_data = queue_data
    except Exception as e:
        queue_data = []
        st.error(f"Queue yüklenemedi: {e}")

    if not queue_data:
        st.info("🎉 Queue boş — incelenecek kayıt yok!")
    else:
        st.caption(f"{len(queue_data)} kayıt")
        for idx, item in enumerate(queue_data):
            icon = FORMULA_ICONS.get(item["formula_name"], "📐")
            preview = (item.get("sentence_text") or "")[:45]
            priority = item.get("priority_score", 0)

            # Verdict badge
            verdict = item.get("human_verdict")
            if verdict == "CORRECTED":
                badge_class = "badge-corrected"
            elif verdict == "CONFIRMED_FAIL":
                badge_class = "badge-confirmed-fail"
            elif verdict == "CONFIRMED_PASS":
                badge_class = "badge-confirmed-pass"
            else:
                badge_class = "badge-pending"

            is_selected = st.session_state.current_log_id == item["log_id"]

            if st.button(
                f"{icon} #{item['log_id']} | {item['formula_name']} | {preview}...",
                key=f"queue_{item['log_id']}_{idx}",
                use_container_width=True,
            ):
                st.session_state.current_log_id = item["log_id"]
                st.rerun()

    # Similar Cases (2.3.3)
    selected_item = None
    if st.session_state.current_log_id and queue_data:
        for item in queue_data:
            if item["log_id"] == st.session_state.current_log_id:
                selected_item = item
                break

    if selected_item:
        with st.expander("🔍 Benzer Vakalar"):
            try:
                similar = run_async(
                    _get_similar_cases(
                        sent_id=selected_item["sent_id"],
                        formula_name=selected_item["formula_name"],
                        country=selected_item.get("country"),
                    )
                )
                if similar:
                    for sc in similar:
                        v_badge = sc.get("human_verdict") or "PENDING"
                        sc_text = (sc.get("sentence_text") or "")[:60]
                        st.markdown(f"- **#{sc['log_id']}** `{v_badge}` — {sc_text}...")
                else:
                    st.caption("Benzer vaka bulunamadı.")
            except Exception:
                st.caption("Benzer vakalar yüklenemedi.")

# ═══════════════════════════════════════════════════════════════════
# CENTER PANEL: Sentence Card + Formula Breakdown + Verdict (2.4.x)
# ═══════════════════════════════════════════════════════════════════

with center_col:
    if selected_item:
        sent_id = selected_item.get("sent_id")
        formula = selected_item["formula_name"]
        icon = FORMULA_ICONS.get(formula, "📐")

        # ── Sentence Card (2.4.1) ─────────────────────────────────
        st.markdown("### 📄 Cümle Bağlamı")

        # Triplet context
        try:
            triplet = run_async(_get_triplet_context(sent_id)) if sent_id else {}
        except Exception:
            triplet = {}

        # Speaker info
        speaker_name = selected_item.get("speaker_name", "Bilinmiyor")
        country = selected_item.get("country", "?")
        power_level = selected_item.get("power_level", 0)

        st.markdown(
            f"<div style='color:#94a3b8; font-size:0.85rem;'>"
            f"🎙️ <b>{speaker_name}</b> ({country}) — Power Level: {power_level}/10"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Triplet display
        verdict_status = selected_item.get("human_verdict")
        if verdict_status == "CORRECTED":
            current_class = "corrected"
        elif verdict_status == "CONFIRMED_PASS":
            current_class = "pass"
        else:
            current_class = "fail"

        prev_text = triplet.get("prev") or ""
        current_text = triplet.get("current") or selected_item.get("sentence_text", "")
        next_text = triplet.get("next") or ""

        triplet_html = """<div class='triplet-container'>"""
        if prev_text:
            triplet_html += f"""<div class='triplet-prev'>⬆ {prev_text}</div>"""
        triplet_html += (
            f"""<div class='triplet-current {current_class}'>▶ {current_text}</div>"""
        )
        if next_text:
            triplet_html += f"""<div class='triplet-next'>⬇ {next_text}</div>"""
        triplet_html += "</div>"
        st.markdown(triplet_html, unsafe_allow_html=True)

        # ── Formula Breakdown (2.4.2) ─────────────────────────────
        st.markdown(f"### {icon} Formül Detayı: `{formula}`")

        expected = selected_item.get("expected_constraint", "?")
        actual = selected_item.get("actual_value", 0)
        details = selected_item.get("details") or {}

        detail_cols = st.columns(3)
        with detail_cols[0]:
            st.metric("Beklenen", expected)
        with detail_cols[1]:
            st.metric("Gerçekleşen", f"{actual:.4f}")
        with detail_cols[2]:
            delta = (
                actual - float(str(expected).split("==")[-1].strip().split()[0])
                if "==" in str(expected)
                else 0
            )
            st.metric("Delta", f"{delta:+.4f}" if delta else "—")

        # Detail JSON breakdown
        if details:
            with st.expander("📋 Detaylı Hesaplama"):
                if isinstance(details, dict):
                    for k, v in details.items():
                        st.markdown(f"- **{k}**: `{v}`")
                else:
                    st.json(details)

        st.divider()

        # ── HITL Verdict Panel (2.4.3) ────────────────────────────
        st.markdown("### ⚖️ Karar")

        verdict_cols = st.columns(3)

        with verdict_cols[0]:
            btn_pass = st.button(
                "✅ AI Doğru\n(CONFIRMED_PASS)",
                key="btn_confirmed_pass",
                use_container_width=True,
            )

        with verdict_cols[1]:
            btn_fail = st.button(
                "❌ AI Yanlış\n(CONFIRMED_FAIL)",
                key="btn_confirmed_fail",
                use_container_width=True,
            )

        with verdict_cols[2]:
            btn_correct = st.button(
                "✏️ Değeri Düzelt\n(CORRECTED)",
                key="btn_corrected",
                use_container_width=True,
            )

        # CORRECTED input
        corrected_value = None
        if btn_correct or st.session_state.get("show_correct_input"):
            st.session_state.show_correct_input = True
            corrected_value = st.number_input(
                "Yeni Değer",
                min_value=0.0,
                max_value=10.0,
                step=0.01,
                value=float(actual) if actual else 0.0,
                key="corrected_value_input",
            )

        # Review note and confidence
        note = st.text_area(
            "📝 İnceleme Notu (opsiyonel)", max_chars=500, key="review_note"
        )
        confidence = st.radio(
            "Güven Seviyesi",
            ["LOW", "MEDIUM", "HIGH"],
            index=1,
            horizontal=True,
            key="confidence_radio",
        )
        justification = st.text_area(
            "📋 Gerekçe (CORRECTED için zorunlu)",
            max_chars=500,
            key="justification_text",
        )

        # Submit verdict
        chosen_verdict = None
        if btn_pass:
            chosen_verdict = "CONFIRMED_PASS"
        elif btn_fail:
            chosen_verdict = "CONFIRMED_FAIL"
        elif btn_correct and corrected_value is not None:
            if not justification:
                st.error("❗ CORRECTED kararı için gerekçe zorunludur!")
            else:
                chosen_verdict = "CORRECTED"

        if chosen_verdict:
            try:
                result = run_async(
                    _submit_verdict(
                        log_id=selected_item["log_id"],
                        verdict=chosen_verdict,
                        corrected_value=(
                            corrected_value if chosen_verdict == "CORRECTED" else None
                        ),
                        note=note or None,
                        confidence=confidence,
                        justification=justification or None,
                        reviewer_id=st.session_state.reviewer_id,
                    )
                )
                st.success(
                    f"✅ Karar kaydedildi! "
                    f"Yeni Log: #{result['new_log_id']} "
                    f"(v{result['log_version']})"
                )
                st.session_state.show_correct_input = False
                st.session_state.current_log_id = None
                st.rerun()
            except Exception as e:
                st.error(f"❌ Karar kaydedilemedi: {e}")

        # ── Navigation (2.4.4) ────────────────────────────────────
        st.divider()
        nav_cols = st.columns(3)
        with nav_cols[0]:
            if st.button("← Önceki", key="nav_prev", use_container_width=True):
                current_idx = next(
                    (
                        i
                        for i, q in enumerate(queue_data)
                        if q["log_id"] == selected_item["log_id"]
                    ),
                    0,
                )
                if current_idx > 0:
                    st.session_state.current_log_id = queue_data[current_idx - 1][
                        "log_id"
                    ]
                    st.rerun()
        with nav_cols[1]:
            st.caption(f"#{selected_item['log_id']} / {len(queue_data)} kayıt")
        with nav_cols[2]:
            if st.button("Sıradaki FAIL →", key="nav_next", use_container_width=True):
                current_idx = next(
                    (
                        i
                        for i, q in enumerate(queue_data)
                        if q["log_id"] == selected_item["log_id"]
                    ),
                    0,
                )
                if current_idx < len(queue_data) - 1:
                    st.session_state.current_log_id = queue_data[current_idx + 1][
                        "log_id"
                    ]
                    st.rerun()

    else:
        st.markdown(
            """
            <div style='text-align:center; padding:80px 20px; color:#64748b;'>
                <div style='font-size:4rem;'>🛡️</div>
                <h3 style='color:#94a3b8 !important;'>HITL Formula Validation</h3>
                <p>Sol panelden bir kayıt seçerek incelemeye başlayın.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ═══════════════════════════════════════════════════════════════════
# RIGHT PANEL: AI Analysis + Speaker Stats + All Formula Logs (2.5.x)
# ═══════════════════════════════════════════════════════════════════

with right_col:
    if selected_item:
        # ── AI Analysis Cards (2.5.1) ─────────────────────────────
        st.markdown("### 🤖 AI Analiz")

        ai_risk = selected_item.get("ai_risk_score")
        ai_emotion = selected_item.get("ai_emotion_category")
        ai_tone = selected_item.get("ai_diplomatic_tone")

        if ai_risk is not None:
            risk_color = (
                "#ef4444" if ai_risk >= 7 else "#f59e0b" if ai_risk >= 4 else "#10b981"
            )
            st.markdown(
                f"""<div class='ai-metric'>
                <div class='metric-label'>🔥 Risk Skoru</div>
                <div class='metric-value' style='color:{risk_color};'>{ai_risk}/10</div>
                </div>""",
                unsafe_allow_html=True,
            )
            st.progress(min(ai_risk / 10.0, 1.0))
        else:
            st.caption("Risk skoru mevcut değil")

        if ai_emotion:
            st.markdown(
                f"""<div class='ai-metric'>
                <div class='metric-label'>🎭 Duygu Kategorisi</div>
                <div class='metric-value'>{ai_emotion}</div>
                </div>""",
                unsafe_allow_html=True,
            )

        if ai_tone:
            st.markdown(
                f"""<div class='ai-metric'>
                <div class='metric-label'>🤝 Diplomatik Ton</div>
                <div class='metric-value'>{ai_tone}</div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Speaker Stats (2.5.2) ─────────────────────────────────
        st.markdown("### 👤 Konuşmacı")

        speaker = selected_item.get("speaker_name", "—")
        country = selected_item.get("country", "—")
        power = selected_item.get("power_level", 0)

        st.markdown(f"**{speaker}** ({country})")
        st.markdown(f"Power Level: **{power}/10**")

        if power >= 9:
            st.error("🔴 TIER1 — Sovereign Priority")
        elif power >= 7:
            st.warning("🟡 TIER2 — High Priority")
        else:
            st.info("🔵 Standard")

        st.divider()

        # ── All Formula Logs for this sentence (2.5.3) ────────────
        st.markdown("### 📋 Tüm Formüller")

        if sent_id and queue_data:
            all_logs_for_sent = [q for q in queue_data if q.get("sent_id") == sent_id]
            if all_logs_for_sent:
                for log in all_logs_for_sent:
                    f_icon = FORMULA_ICONS.get(log["formula_name"], "📐")
                    status = log.get("status", "?")
                    verdict = log.get("human_verdict")
                    badge = verdict or status
                    badge_cls = "badge-pass" if status == "PASS" else "badge-fail"
                    if verdict:
                        badge_cls = f"badge-{verdict.lower().replace('_', '-')}"
                    st.markdown(
                        f"{f_icon} **{log['formula_name']}** "
                        f"<span class='badge {badge_cls}'>{badge}</span> "
                        f"— `{log.get('actual_value', 0):.3f}`",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Bu cümle için ek formül logu yok.")

# ═══════════════════════════════════════════════════════════════════
# BOTTOM: Audit Trail (2.6.1, 2.6.2)
# ═══════════════════════════════════════════════════════════════════

st.divider()

with st.expander("🕐 Audit Trail (Son 10 İşlem)", expanded=False):
    try:
        audit_trail = run_async(_get_audit_trail(limit=10))
        if audit_trail:
            for entry in audit_trail:
                performed_at = entry.get("performed_at", "?")
                if isinstance(performed_at, str) and "T" in performed_at:
                    performed_at = performed_at.split("T")[1][:5]
                action = entry.get("action_type", "?")
                performer = entry.get("performed_by", "?")
                prev_v = entry.get("previous_verdict") or "—"
                new_v = entry.get("new_verdict") or "—"

                action_icons = {
                    "REVIEW_STARTED": "🔍",
                    "VERDICT_SUBMITTED": "⚖️",
                    "CORRECTED": "✏️",
                    "ROLLED_BACK": "↩️",
                    "ESCALATED": "🚨",
                }
                a_icon = action_icons.get(action, "📝")

                st.markdown(
                    f"`[{performed_at}]` {a_icon} **{performer}** → "
                    f"`{action}` on log #{entry.get('log_id', '?')} | "
                    f"{prev_v} → {new_v}"
                )
        else:
            st.caption("Henüz audit kaydı yok.")
    except Exception:
        st.caption("Audit trail yüklenemedi.")

# ── Footer ───────────────────────────────────────────────────────────

st.markdown(
    "<div style='text-align:center; color:#475569; padding:20px; font-size:0.8rem;'>"
    "HITL Formula Validation Dashboard v2.0 — PAXDATA"
    "</div>",
    unsafe_allow_html=True,
)
