from typing import Any

import streamlit as st

from dashboard.queries import get_filter_bounds


def render_sidebar() -> dict[str, Any]:
    """Render global sidebar filters and return user selections."""
    st.sidebar.title("⚡ FinPulse Analytics")
    st.sidebar.markdown("---")

    bounds = get_filter_bounds()
    min_date = bounds["min_date"]
    max_date = bounds["max_date"]

    st.sidebar.subheader("📅 Date Range")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

    if start_date > end_date:
        st.sidebar.error("Start date must be earlier than or equal to End date.")
        start_date, end_date = min_date, max_date

    st.sidebar.subheader("👤 User Selection")
    user_options = ["All Users"] + bounds["users"]
    selected_user_idx = st.sidebar.selectbox("User ID", options=user_options, index=0)
    selected_user = None if selected_user_idx == "All Users" else selected_user_idx

    st.sidebar.subheader("💱 Currency")
    currency_options = bounds["currencies"] if bounds["currencies"] else ["INR"]
    selected_currency = st.sidebar.selectbox("Currency", options=currency_options, index=0)

    if st.sidebar.button("🔄 Reset Filters", use_container_width=True):
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption("FinPulse v0.1.0 • DuckDB + dbt Engine")

    return {
        "start_date": start_date,
        "end_date": end_date,
        "user_id": selected_user,
        "currency": selected_currency,
    }
