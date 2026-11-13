import streamlit as st

from dashboard.components.charts import (
    plot_category_distribution,
    plot_income_vs_expenses,
    plot_spending_trend,
    plot_top_merchants,
)
from dashboard.components.kpi_cards import render_kpi_cards
from dashboard.components.sidebar import render_sidebar
from dashboard.config import config
from dashboard.database import is_database_available
from dashboard.queries import (
    get_category_spending,
    get_daily_spending_trend,
    get_merchant_spending,
    get_overview_kpis,
)

st.set_page_config(page_title="Overview | FinPulse", page_icon=config.app_icon, layout="wide")

st.title("📊 Executive Financial Overview")

if not is_database_available():
    st.error("Warehouse database not available. Please run the pipeline first.")
    st.stop()

filters = render_sidebar()
currency = filters["currency"]

# Fetch KPIs
kpis = get_overview_kpis(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    currency=currency,
)

# Render KPI Cards
render_kpi_cards(kpis, currency=currency)

st.markdown("---")

# Fetch time series & category data
df_daily = get_daily_spending_trend(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    currency=currency,
)

df_cat = get_category_spending(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    currency=currency,
)

df_merchants = get_merchant_spending(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    currency=currency,
    limit=8,
)

# Row 1: Income vs. Expenses and Category Breakdown
chart_col1, chart_col2 = st.columns([1.5, 1])

with chart_col1:
    fig_line = plot_income_vs_expenses(df_daily, currency=currency)
    st.plotly_chart(fig_line, use_container_width=True)

with chart_col2:
    fig_cat = plot_category_distribution(df_cat, currency=currency)
    st.plotly_chart(fig_cat, use_container_width=True)

# Row 2: Net Cash Flow Trend and Top Merchants
chart_col3, chart_col4 = st.columns([1.2, 1.2])

with chart_col3:
    fig_flow = plot_spending_trend(df_daily, currency=currency)
    st.plotly_chart(fig_flow, use_container_width=True)

with chart_col4:
    fig_merch = plot_top_merchants(df_merchants, currency=currency)
    st.plotly_chart(fig_merch, use_container_width=True)

