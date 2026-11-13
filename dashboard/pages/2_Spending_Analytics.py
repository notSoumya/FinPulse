import plotly.express as px
import streamlit as st

from dashboard.components.charts import plot_category_distribution
from dashboard.components.sidebar import render_sidebar
from dashboard.config import config
from dashboard.database import is_database_available
from dashboard.metrics import format_currency, format_number
from dashboard.queries import get_category_spending, get_daily_spending_trend

st.set_page_config(
    page_title="Spending Analytics | FinPulse",
    page_icon=config.app_icon,
    layout="wide",
)

st.title("💸 Spending & Category Analytics")

if not is_database_available():
    st.error("Warehouse database not available. Please run the pipeline first.")
    st.stop()

filters = render_sidebar()
currency = filters["currency"]

df_cat = get_category_spending(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    currency=currency,
)

col1, col2 = st.columns([1, 1.2])

with col1:
    fig_pie = plot_category_distribution(df_cat, currency=currency)
    st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    if not df_cat.empty:
        fig_bar = px.bar(
            df_cat,
            x="spending_category",
            y="total_spent",
            color="spending_category",
            title="Expenditure by Category",
            text_auto=",.2f",
        )
        fig_bar.update_layout(
            xaxis_title="Category",
            yaxis_title=f"Total Amount ({currency})",
            template="plotly_white",
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No category data found for the selected period.")

st.markdown("### 📋 Category Breakdown Table")
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

st.markdown("---")
st.subheader("📈 Daily Outflow Timeline")
df_daily = get_daily_spending_trend(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    currency=currency,
)

if not df_daily.empty:
    fig_timeline = px.area(
        df_daily,
        x="transaction_date",
        y="expenses",
        title="Daily Expense Outflow Trajectory",
        color_discrete_sequence=["#d62728"],
    )
    fig_timeline.update_layout(
        xaxis_title="Date",
        yaxis_title=f"Expenses ({currency})",
        template="plotly_white",
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

