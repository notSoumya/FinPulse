import plotly.express as px
import streamlit as st

from dashboard.components.charts import plot_monthly_cashflow
from dashboard.components.sidebar import render_sidebar
from dashboard.config import config
from dashboard.database import is_database_available
from dashboard.metrics import format_currency, format_number
from dashboard.queries import get_cashflow_summary, get_monthly_spending_trend

st.set_page_config(
    page_title="Cash Flow Analytics | FinPulse",
    page_icon=config.app_icon,
    layout="wide",
)

st.title("💵 Cash Flow & Income vs. Expense Dynamics")

if not is_database_available():
    st.error("Warehouse database not available. Please run the pipeline first.")
    st.stop()

filters = render_sidebar()
currency = filters["currency"]

# Fetch cashflow summary
df_cf = get_cashflow_summary(user_id=filters["user_id"], currency=currency)

col1, col2 = st.columns([1.5, 1])

with col1:
    df_monthly = get_monthly_spending_trend(user_id=filters["user_id"], currency=currency)
    fig_monthly = plot_monthly_cashflow(df_monthly, currency=currency)
    st.plotly_chart(fig_monthly, use_container_width=True)

with col2:
    if not df_cf.empty:
        fig_donut = px.pie(
            df_cf,
            values="total_volume",
            names="direction",
            title="Total Volume: DEBIT vs. CREDIT",
            hole=0.5,
            color="direction",
            color_discrete_map={"DEBIT": "#d62728", "CREDIT": "#2ca02c"},
        )
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("No cash flow volume recorded.")

st.markdown("### 📋 Directional Flow Breakdown")
if not df_cf.empty:
    cf_display = df_cf.copy()
    cf_display["Total Volume"] = cf_display["total_volume"].apply(
        lambda v: format_currency(v, currency)
    )
    cf_display["Avg Transaction"] = cf_display["avg_amount"].apply(
        lambda v: format_currency(v, currency)
    )
    cf_display["Min Amount"] = cf_display["min_amount"].apply(
        lambda v: format_currency(v, currency)
    )
    cf_display["Max Amount"] = cf_display["max_amount"].apply(
        lambda v: format_currency(v, currency)
    )
    cf_display["Transaction Count"] = cf_display["transaction_count"].apply(format_number)

    cols = [
        "direction",
        "Total Volume",
        "Transaction Count",
        "Avg Transaction",
        "Min Amount",
        "Max Amount",
    ]
    st.dataframe(
        cf_display[cols],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No cash flow data available.")
