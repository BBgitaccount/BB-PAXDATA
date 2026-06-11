import streamlit as st

from hitl.db_helpers import _get_audit_trail, run_async


def render_audit_trail():
    """Renders the bottom audit trail panel showing the last 10 human reviewer operations."""
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
