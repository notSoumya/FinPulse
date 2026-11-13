from typing import Any

import streamlit as st

from dashboard.metrics import format_currency, format_number, format_pct


def render_kpi_cards(kpis: dict[str, Any], currency: str = "INR"):
    """Render financial KPI metric cards across 6 columns."""
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric(
            label="Total Income",
            value=format_currency(kpis.get("total_income"), currency),
        )
    with col2:
        st.metric(
            label="Total Expenses",
            value=format_currency(kpis.get("total_expenses"), currency),
        )
    with col3:
        net_cf = kpis.get("net_cash_flow") or 0
        delta_color = "normal" if net_cf >= 0 else "inverse"
        st.metric(
            label="Net Cash Flow",
            value=format_currency(net_cf, currency),
            delta=f"{format_currency(net_cf, currency)} Net",
            delta_color=delta_color,
        )
    with col4:
        savings_rate = kpis.get("savings_rate_pct")
        st.metric(
            label="Savings Rate",
            value=format_pct(savings_rate),
        )
    with col5:
        st.metric(
            label="Total Transactions",
            value=format_number(kpis.get("total_transactions")),
        )
    with col6:
        avg_val = kpis.get("avg_transaction_value")
        st.metric(
            label="Avg Ticket Size",
            value=format_currency(avg_val, currency),
        )

