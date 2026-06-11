import streamlit as st

from hitl.config import FORMULA_ICONS


def render_ai_analysis(selected_item, queue_data):
    """Renders the AI metrics, speaker profile, and all formula logs for the selected sentence."""
    if selected_item:
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

        # ── Speaker Stats ──
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

        # ── All Formula Logs for this sentence ──
        st.markdown("### 📋 Tüm Formüller")

        sent_id = selected_item.get("sent_id")
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
