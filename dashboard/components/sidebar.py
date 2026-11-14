import calendar
from datetime import date
from typing import Any

import streamlit as st

from dashboard.queries import get_filter_bounds


def render_sidebar() -> dict[str, Any]:
    """Render global sidebar filters and return comprehensive user selections."""
    st.sidebar.title("⚡ FinPulse Analytics")
    st.sidebar.markdown("---")

    bounds = get_filter_bounds()
    min_date = bounds["min_date"]
    max_date = bounds["max_date"]

    # 1. User Selection
    st.sidebar.subheader("👤 User Selection")
    user_options = ["All Users"] + bounds["users"]
    selected_user_idx = st.sidebar.selectbox("User Account", options=user_options, index=0)
    selected_user = None if selected_user_idx == "All Users" else selected_user_idx

    # 2. Month Quick Filter
    st.sidebar.subheader("📆 Calendar Month")
    month_options = ["All Months"] + bounds.get("months", [])
    selected_month = st.sidebar.selectbox("Month Filter", options=month_options, index=0)

    # Date range default logic: if specific month chosen, narrow default start/end
    default_start = min_date
    default_end = max_date
    if selected_month != "All Months":
        try:
            yr, mo = map(int, selected_month.split("-"))
            _, last_day = calendar.monthrange(yr, mo)
            default_start = max(date(yr, mo, 1), min_date)
            default_end = min(date(yr, mo, last_day), max_date)
        except Exception:
            pass

    # 3. Date Range
    st.sidebar.subheader("📅 Date Range")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "From", value=default_start, min_value=min_date, max_value=max_date
        )
    with col2:
        end_date = st.date_input("To", value=default_end, min_value=min_date, max_value=max_date)

    if start_date > end_date:
        st.sidebar.error("Start date must be earlier than or equal to End date.")
        start_date, end_date = min_date, max_date

    # 4. Spending Category Filter
    st.sidebar.subheader("🏷️ Category & Channel")
    cat_options = ["All Categories"] + bounds.get("categories", [])
    selected_cat = st.sidebar.selectbox("Category", options=cat_options, index=0)
    category_filter = None if selected_cat == "All Categories" else selected_cat

    # 5. Transaction Source Filter
    source_options = ["All Sources"] + bounds.get("sources", [])
    selected_src = st.sidebar.selectbox("Source Channel", options=source_options, index=0)
    source_filter = None if selected_src == "All Sources" else selected_src

    # 6. Direction & Merchant
    st.sidebar.subheader("💳 Direction & Merchant")
    direction_options = ["ALL", "DEBIT", "CREDIT"]
    selected_direction = st.sidebar.selectbox("Flow Direction", options=direction_options, index=0)

    merchant_options = ["All Merchants"] + bounds.get("merchants", [])
    selected_merchant = st.sidebar.selectbox("Merchant", options=merchant_options, index=0)
    merchant_filter = None if selected_merchant == "All Merchants" else selected_merchant

    # 7. Currency
    currency_options = bounds["currencies"] if bounds["currencies"] else ["INR"]
    selected_currency = st.sidebar.selectbox("Currency", options=currency_options, index=0)

    if st.sidebar.button("🔄 Reset Filters", use_container_width=True):
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption("FinPulse v0.1.0 • DuckDB + dbt + ML Engine")

    return {
        "start_date": start_date,
        "end_date": end_date,
        "user_id": selected_user,
        "month": selected_month,
        "category": category_filter,
        "source_type": source_filter,
        "direction": selected_direction,
        "merchant": merchant_filter,
        "currency": selected_currency,
    }
