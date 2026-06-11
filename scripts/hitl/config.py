import streamlit as st

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
          border-left: 3px solid;
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
