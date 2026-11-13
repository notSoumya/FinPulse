import streamlit as st

from dashboard.components.sidebar import render_sidebar
from dashboard.config import config
from dashboard.database import is_database_available
from dashboard.queries import get_data_freshness, get_overview_kpis

st.set_page_config(
    page_title=config.app_title,
    page_icon=config.app_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("⚡ FinPulse Financial Intelligence Platform")
st.markdown(
    """
    Welcome to **FinPulse Analytics**. This platform provides real-time and historical
    financial intelligence modeled through an end-to-end lakehouse pipeline
    (**Bronze JSONL → Silver Delta Lake → DuckDB Warehouse → dbt Gold Marts**).
    """
)

# Global Sidebar
filters = render_sidebar()

# System Status & Warehouse Connectivity
st.subheader("🔍 Warehouse & System Health")
db_online = is_database_available()

status_col1, status_col2, status_col3 = st.columns(3)
with status_col1:
    if db_online:
        st.success("✅ DuckDB Analytical Warehouse: Online")
    else:
        st.error("❌ Warehouse Database: Not Found")

with status_col2:
    freshness = get_data_freshness()
    latest_ts = freshness["latest_processed_at"]
    if latest_ts:
        st.info(f"🕒 Pipeline Freshness: {latest_ts}")
    else:
        st.info("🕒 Pipeline Freshness: No pipeline sync recorded yet")

with status_col3:
    st.info(f"📊 Curated Silver Records: {freshness['total_rows']:,}")

st.markdown("---")

if not db_online:
    st.warning(
        """
        **DuckDB warehouse not initialized yet.**
        Please run the FinPulse data pipeline to populate the warehouse:
        ```bash
        python scripts/run_silver_pipeline.py
        python scripts/run_warehouse.py
        ```
        """
    )
else:
    st.markdown("### 📌 Quick KPI Summary")
    kpis = get_overview_kpis(
        start_date=filters["start_date"],
        end_date=filters["end_date"],
        user_id=filters["user_id"],
        currency=filters["currency"],
    )
    from dashboard.components.kpi_cards import render_kpi_cards

    render_kpi_cards(kpis, currency=filters["currency"])

    st.markdown("---")
    st.markdown("### 🧭 Navigation Guide")
    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        st.markdown("**1. Financial Overview**")
        st.caption("Complete income, expense, cash flow, and trend snapshot.")
    with nav2:
        st.markdown("**2. Spending Analytics**")
        st.caption("Category distributions, top spenders, and timeline dynamics.")
    with nav3:
        st.markdown("**3. Merchant Intelligence**")
        st.caption("Merchant outflows, frequencies, and ticket size analytics.")
    with nav4:
        st.markdown("**4. Transaction Explorer**")
        st.caption("Search, filter, and inspect individual curated transactions.")
