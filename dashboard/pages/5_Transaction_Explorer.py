import streamlit as st

from dashboard.components.sidebar import render_sidebar
from dashboard.components.tables import render_transactions_table
from dashboard.config import config
from dashboard.database import is_database_available
from dashboard.queries import get_filtered_transactions

st.set_page_config(
    page_title="Transaction Explorer | FinPulse",
    page_icon=config.app_icon,
    layout="wide",
)

st.title("🔎 Transaction Explorer")
st.markdown("Search, filter, and inspect curated transactions directly from `silver.transactions`.")

if not is_database_available():
    st.error("Warehouse database not available. Please run the pipeline first.")
    st.stop()

filters = render_sidebar()
currency = filters["currency"]

ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1.5, 1, 1])
with ctrl_col1:
    search_term = st.text_input(
        "🔍 Search Merchant / Description",
        placeholder="e.g. Amazon, Swiggy...",
    )
with ctrl_col2:
    direction_filter = st.selectbox("Flow Direction", options=["ALL", "DEBIT", "CREDIT"], index=0)
with ctrl_col3:
    page_size = st.selectbox("Page Size", options=[25, 50, 100], index=1)

df_txns, total_count = get_filtered_transactions(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    direction=direction_filter,
    merchant_search=search_term,
    currency=currency,
    limit=page_size,
    offset=0,
)

st.caption(f"Showing {len(df_txns)} of {total_count:,} matching transactions")

render_transactions_table(df_txns, currency=currency)
