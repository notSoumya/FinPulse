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
st.markdown(
    "Search, filter, and inspect curated transactions with "
    "ML anomaly indicators directly from the warehouse."
)

if not is_database_available():
    st.error("Warehouse database not available. Please run the pipeline first.")
    st.stop()

filters = render_sidebar()
currency = filters["currency"]

ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([1.5, 1, 1, 1])
with ctrl_col1:
    search_term = st.text_input(
        "🔍 Search Merchant / Description",
        placeholder="e.g. Amazon, Swiggy...",
    )
with ctrl_col2:
    direction_filter = st.selectbox(
        "Direction Filter",
        options=["ALL", "DEBIT", "CREDIT"],
        index=0
        if not filters.get("direction")
        else ["ALL", "DEBIT", "CREDIT"].index(filters["direction"]),
    )
with ctrl_col3:
    status_filter = st.selectbox(
        "Anomaly Filter",
        options=["All Statuses", "Anomalies Only", "Normal Only"],
        index=0,
    )
with ctrl_col4:
    page_size = st.selectbox("Page Size", options=[25, 50, 100], index=1)

df_txns, total_count = get_filtered_transactions(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    direction=direction_filter,
    merchant_search=search_term,
    category=filters.get("category"),
    source_type=filters.get("source_type"),
    currency=currency,
    limit=page_size,
    offset=0,
)

if status_filter == "Anomalies Only" and not df_txns.empty and "is_anomaly" in df_txns.columns:
    df_txns = df_txns[df_txns["is_anomaly"]].reset_index(drop=True)
elif status_filter == "Normal Only" and not df_txns.empty and "is_anomaly" in df_txns.columns:
    df_txns = df_txns[~df_txns["is_anomaly"]].reset_index(drop=True)

st.caption(f"Showing {len(df_txns)} of {total_count:,} matching transactions")

render_transactions_table(df_txns, currency=currency)

if not df_txns.empty:
    st.markdown("---")
    st.subheader("🔍 Transaction Detail Inspector")
    txn_options = [
        f"{r['transaction_id']} | {r['transaction_date']} | "
        f"{r['merchant_name']} | {currency} {float(r['amount']):,.2f}"
        for _, r in df_txns.iterrows()
    ]
    selected_idx = st.selectbox(
        "Select Transaction to Inspect",
        options=range(len(txn_options)),
        format_func=lambda i: txn_options[i],
    )
    selected_txn = df_txns.iloc[selected_idx]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**Transaction ID:** `{selected_txn['transaction_id']}`")
        st.markdown(f"**Date:** {selected_txn['transaction_date']}")
        st.markdown(f"**Merchant:** **{selected_txn['merchant_name']}**")
    with c2:
        st.markdown(f"**Amount:** {currency} {float(selected_txn['amount']):,.2f}")
        st.markdown(f"**Direction:** `{selected_txn['direction']}`")
        st.markdown(f"**Category:** {selected_txn.get('category', 'N/A')}")
    with c3:
        st.markdown(f"**Source:** `{selected_txn['source_type']}`")
        if "is_anomaly" in selected_txn:
            status_badge = "🔴 Flagged Anomaly" if selected_txn["is_anomaly"] else "🟢 Normal"
            st.markdown(f"**Anomaly Status:** {status_badge}")
            score_val = float(selected_txn.get("anomaly_score", 0.0))
            sev_val = selected_txn.get("severity", "Normal")
            st.markdown(f"**Score:** `{score_val:.3f}` ({sev_val})")
