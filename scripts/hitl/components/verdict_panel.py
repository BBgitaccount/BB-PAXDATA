import streamlit as st

from hitl.config import FORMULA_ICONS
from hitl.db_helpers import _get_triplet_context, _submit_verdict, run_async


def render_verdict_panel(selected_item, queue_data):
    """Renders the central workspace containing sentence context and verdict forms."""
    if selected_item:
        sent_id = selected_item.get("sent_id")
        formula = selected_item["formula_name"]
        icon = FORMULA_ICONS.get(formula, "📐")

        # ── Sentence Card ──
        st.markdown("### 📄 Cümle Bağlamı")

        # Triplet display
        try:
            triplet = run_async(_get_triplet_context(sent_id)) if sent_id else {}
        except Exception:
            triplet = {}

        speaker_name = selected_item.get("speaker_name", "Bilinmiyor")
        country = selected_item.get("country", "?")
        power_level = selected_item.get("power_level", 0)

        st.markdown(
            f"<div style='color:#94a3b8; font-size:0.85rem;'>"
            f"🎙️ <b>{speaker_name}</b> ({country}) — Power Level: {power_level}/10"
            f"</div>",
            unsafe_allow_html=True,
        )

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

        triplet_html = "<div class='triplet-container'>"
        if prev_text:
            triplet_html += f"<div class='triplet-prev'>⬆ {prev_text}</div>"
        triplet_html += (
            f"<div class='triplet-current {current_class}'>▶ {current_text}</div>"
        )
        if next_text:
            triplet_html += f"<div class='triplet-next'>⬇ {next_text}</div>"
        triplet_html += "</div>"
        st.markdown(triplet_html, unsafe_allow_html=True)

        # ── Formula Breakdown ──
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
            try:
                # Parse expected value to show delta
                clean_exp = str(expected).split("==")[-1].strip().split()[0]
                delta = actual - float(clean_exp)
                st.metric("Delta", f"{delta:+.4f}")
            except Exception:
                st.metric("Delta", "—")

        if details:
            with st.expander("📋 Detaylı Hesaplama"):
                if isinstance(details, dict):
                    for k, v in details.items():
                        st.markdown(f"- **{k}**: `{v}`")
                else:
                    st.json(details)

        st.divider()

        # ── HITL Verdict Panel ──
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

        # CORRECTED input toggling
        if "show_correct_input" not in st.session_state:
            st.session_state.show_correct_input = False

        if btn_correct:
            st.session_state.show_correct_input = True

        corrected_value = None
        if st.session_state.show_correct_input:
            corrected_value = st.number_input(
                "Yeni Değer",
                min_value=0.0,
                max_value=10.0,
                step=0.01,
                value=float(actual) if actual else 0.0,
                key="corrected_value_input",
            )

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
                    f"✅ Karar kaydedildi! Yeni Log: #{result['new_log_id']} (v{result['log_version']})"
                )
                st.session_state.show_correct_input = False
                st.session_state.current_log_id = None
                st.rerun()
            except Exception as e:
                st.error(f"❌ Karar kaydedilemedi: {e}")

        # ── Navigation ──
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
