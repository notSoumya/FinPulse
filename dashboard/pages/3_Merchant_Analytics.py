import plotly.express as px
import streamlit as st

from dashboard.components.charts import plot_top_merchants
from dashboard.components.sidebar import render_sidebar
from dashboard.config import config
from dashboard.database import is_database_available
from dashboard.metrics import format_currency, format_number
from dashboard.queries import get_merchant_spending

st.set_page_config(
    page_title="Merchant Analytics | FinPulse",
    page_icon=config.app_icon,
    layout="wide",
)

st.title("🏬 Merchant Intelligence & Analytics")

if not is_database_available():
    st.error("Warehouse database not available. Please run the pipeline first.")
    st.stop()

filters = render_sidebar()
currency = filters["currency"]

col_ctrl1, col_ctrl2 = st.columns([2, 1])
with col_ctrl1:
    merchant_limit = st.slider(
        "Number of Top Merchants to Display",
        min_value=5,
        max_value=25,
        value=10,
    )

df_merchants = get_merchant_spending(
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    user_id=filters["user_id"],
    currency=currency,
    limit=merchant_limit,
)

if df_merchants.empty:
    st.info("No merchant spending data found matching the selected filters.")
    st.stop()

col_chart1, col_chart2 = st.columns([1.5, 1])

with col_chart1:
    fig_bar = plot_top_merchants(df_merchants, currency=currency)
    st.plotly_chart(fig_bar, use_container_width=True)

with col_chart2:
    fig_scatter = px.scatter(
        df_merchants,
        x="transaction_count",
        y="avg_ticket_size",
        size="total_spent",
        color="merchant_name",
        hover_name="merchant_name",
        title="Transaction Frequency vs. Avg Ticket Size",
    )
    fig_scatter.update_layout(
        xaxis_title="Transaction Count",
        yaxis_title=f"Avg Ticket Size ({currency})",
        template="plotly_white",
        showlegend=False,
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("### 📋 Merchant Expenditure Summary Table")
table_df = df_merchants.copy()
table_df["Total Spent"] = table_df["total_spent"].apply(
    lambda v: format_currency(v, currency)
)
table_df["Avg Ticket Size"] = table_df["avg_ticket_size"].apply(
    lambda v: format_currency(v, currency)
)
table_df["Transaction Count"] = table_df["transaction_count"].apply(format_number)

cols_to_show = ["merchant_name", "Total Spent", "Transaction Count", "Avg Ticket Size"]
if "first_purchase_date" in table_df.columns:
    cols_to_show.extend(["first_purchase_date", "last_purchase_date"])

st.dataframe(
    table_df[cols_to_show],
    use_container_width=True,
    hide_index=True,
)
