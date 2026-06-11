import streamlit as st

from hitl.config import FORMULA_ICONS
from hitl.db_helpers import _get_fail_queue, _get_similar_cases, run_async


def render_sidebar_queue():
    """Renders the filters and failure queue in the sidebar."""
    st.markdown("### 🔍 Filtreler")

    # Formula filter
    formula_names = ["Tümü", *FORMULA_ICONS.keys()]

    # Sync filter state
    if "filter_formula" not in st.session_state:
        st.session_state.filter_formula = "Tümü"

    filter_formula = st.selectbox(
        "Formül",
        formula_names,
        key="formula_filter_select",
    )
    st.session_state.filter_formula = filter_formula

    # Status filter
    status_options = {"Bekleyen": "unreviewed", "İncelenen": "reviewed", "Tümü": "all"}

    if "filter_status" not in st.session_state:
        st.session_state.filter_status = "Bekleyen"

    filter_status = st.radio(
        "Durum",
        list(status_options.keys()),
        horizontal=True,
        key="status_filter_radio",
    )
    st.session_state.filter_status = filter_status

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

    selected_item = None

    # Handle current selection
    if st.session_state.current_log_id and queue_data:
        for item in queue_data:
            if item["log_id"] == st.session_state.current_log_id:
                selected_item = item
                break

    if not queue_data:
        st.info("🎉 Queue boş — incelenecek kayıt yok!")
    else:
        st.caption(f"{len(queue_data)} kayıt")
        for idx, item in enumerate(queue_data):
            icon = FORMULA_ICONS.get(item["formula_name"], "📐")
            preview = (item.get("sentence_text") or "")[:45]

            is_selected = st.session_state.current_log_id == item["log_id"]

            # Highlight if selected
            button_label = (
                f"{icon} #{item['log_id']} | {item['formula_name']} | {preview}..."
            )
            if is_selected:
                button_label = f"👉 {button_label}"

            if st.button(
                button_label,
                key=f"queue_{item['log_id']}_{idx}",
                use_container_width=True,
            ):
                st.session_state.current_log_id = item["log_id"]
                st.rerun()

    # Similar Cases
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

    return queue_data, selected_item
