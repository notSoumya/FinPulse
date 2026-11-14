import plotly.express as px
import streamlit as st

from dashboard.components.charts import (
    plot_category_distribution,
    plot_debit_credit_distribution,
    plot_monthly_cashflow,
    plot_spending_by_source,
    plot_top_merchants,
)
from dashboard.components.sidebar import render_sidebar
from dashboard.config import config
from dashboard.database import is_database_available
from dashboard.metrics import format_currency, format_number
from dashboard.queries import (
    get_cashflow_summary,
    get_category_spending,
    get_daily_spending_trend,
    get_merchant_spending,
    get_monthly_spending_trend,
    get_spending_by_source,
)

st.set_page_config(
    page_title="Spending Analytics | FinPulse",
    page_icon=config.app_icon,
    layout="wide",
)

st.title("💸 Spending & Cash Flow Analytics")

if not is_database_available():
    st.error("Warehouse database not available. Please run the pipeline first.")
    st.stop()

filters = render_sidebar()
currency = filters["currency"]

# Fetch data for spending analyses
df_cat = get_category_spending(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    source_type=filters.get("source_type"),
    currency=currency,
)

df_merchants = get_merchant_spending(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    currency=currency,
    limit=8,
)

df_source = get_spending_by_source(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    currency=currency,
)

df_cf = get_cashflow_summary(user_id=filters["user_id"], currency=currency)

df_monthly = get_monthly_spending_trend(user_id=filters["user_id"], currency=currency)

# Section 1: Category & Merchant Breakdown
st.subheader("1. Category & Merchant Spending Dynamics")
row1_col1, row1_col2 = st.columns([1.2, 1.2])

with row1_col1:
    fig_pie = plot_category_distribution(df_cat, currency=currency)
    st.plotly_chart(fig_pie, use_container_width=True)

with row1_col2:
    fig_merch = plot_top_merchants(df_merchants, currency=currency)
    st.plotly_chart(fig_merch, use_container_width=True)

# Section 2: Channel & Flow Distribution
st.markdown("---")
st.subheader("2. Source Channels & Cash Flow Distribution")
row2_col1, row2_col2 = st.columns([1.2, 1.2])

with row2_col1:
    fig_src = plot_spending_by_source(df_source, currency=currency)
    st.plotly_chart(fig_src, use_container_width=True)

with row2_col2:
    fig_donut = plot_debit_credit_distribution(df_cf, currency=currency)
    st.plotly_chart(fig_donut, use_container_width=True)

# Section 3: Monthly Cash Flow & Daily Outflow Trajectory
st.markdown("---")
st.subheader("3. Temporal Trends & Monthly Dynamics")
row3_col1, row3_col2 = st.columns([1.3, 1.1])

with row3_col1:
    fig_monthly = plot_monthly_cashflow(df_monthly, currency=currency)
    st.plotly_chart(fig_monthly, use_container_width=True)

with row3_col2:
    df_daily = get_daily_spending_trend(
        start_date=filters["start_date"],
        end_date=filters["end_date"],
        user_id=filters["user_id"],
        category=filters.get("category"),
        source_type=filters.get("source_type"),
        currency=currency,
    )
    if not df_daily.empty:
        fig_daily = px.area(
            df_daily,
            x="transaction_date",
            y="expenses",
            title="Daily Expense Outflow Trajectory",
            color_discrete_sequence=["#d62728"],
        )
        fig_daily.update_layout(
            xaxis_title="Date",
            yaxis_title=f"Expenses ({currency})",
            template="plotly_white",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_daily, use_container_width=True)
    else:
        st.info("No daily spending recorded for this window.")

# Section 4: Detailed Category Breakdown Table
st.markdown("---")
st.subheader("4. Category Breakdown Table")
if not df_cat.empty:
    total_spend = df_cat["total_spent"].sum()
    table_df = df_cat.copy()
    table_df["Share %"] = (table_df["total_spent"] / total_spend * 100).round(2).astype(str) + "%"
    table_df["Total Spent"] = table_df["total_spent"].apply(lambda v: format_currency(v, currency))
    table_df["Avg Amount"] = table_df["avg_amount"].apply(lambda v: format_currency(v, currency))
    table_df["Transactions"] = table_df["transaction_count"].apply(format_number)

    st.dataframe(
        table_df[["spending_category", "Total Spent", "Share %", "Avg Amount", "Transactions"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No spending records available.")
