from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def plot_income_vs_expenses(df: pd.DataFrame, currency: str = "INR") -> go.Figure:
    """Line chart comparing daily income vs. daily expenses."""
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(
            go.Scatter(
                x=df["transaction_date"],
                y=df["income"],
                name="Income",
                line=dict(color="#2ca02c", width=2),
                mode="lines+markers",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["transaction_date"],
                y=df["expenses"],
                name="Expenses",
                line=dict(color="#d62728", width=2),
                mode="lines+markers",
            )
        )

    fig.update_layout(
        title="Income vs. Expenses Over Time",
        xaxis_title="Date",
        yaxis_title=f"Amount ({currency})",
        hovermode="x unified",
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def plot_spending_trend(df: pd.DataFrame, currency: str = "INR") -> go.Figure:
    """Bar / line chart showing daily net cash flow."""
    fig = go.Figure()
    if not df.empty:
        colors = ["#2ca02c" if val >= 0 else "#d62728" for val in df["net_cash_flow"]]
        fig.add_trace(
            go.Bar(
                x=df["transaction_date"],
                y=df["net_cash_flow"],
                name="Net Cash Flow",
                marker_color=colors,
            )
        )

    fig.update_layout(
        title="Daily Net Cash Flow Trend",
        xaxis_title="Date",
        yaxis_title=f"Net Flow ({currency})",
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def plot_category_distribution(df: pd.DataFrame, currency: str = "INR") -> go.Figure:
    """Donut chart showing spending breakdown by category."""
    if df.empty or df["total_spent"].sum() == 0:
        fig = go.Figure()
        fig.update_layout(title="Spending by Category (No Data Available)")
        return fig

    fig = px.pie(
        df,
        values="total_spent",
        names="spending_category",
        title="Spending Distribution by Category",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Prism,
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate=(
            f"<b>%{{label}}</b><br>Amount: {currency} %{{value:,.2f}}<br>Share: %{{percent}}"
        ),
    )
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def plot_top_merchants(df: pd.DataFrame, currency: str = "INR") -> go.Figure:
    """Horizontal bar chart showing top merchants by total spend."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Top Merchants by Spending (No Data Available)")
        return fig

    df_sorted = df.sort_values(by="total_spent", ascending=True)

    fig = px.bar(
        df_sorted,
        x="total_spent",
        y="merchant_name",
        orientation="h",
        title="Top Merchants by Expenditure",
        text_auto=",.2f",
        color="total_spent",
        color_continuous_scale="Blues",
    )
    fig.update_layout(
        xaxis_title=f"Total Outflow ({currency})",
        yaxis_title="Merchant",
        template="plotly_white",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def plot_monthly_cashflow(df: pd.DataFrame, currency: str = "INR") -> go.Figure:
    """Grouped bar chart showing monthly income, expenses, and net savings."""
    fig = go.Figure()
    if not df.empty:
        df_copy = df.copy()
        df_copy["month_label"] = pd.to_datetime(df_copy["transaction_month"]).dt.strftime("%b %Y")
        fig.add_trace(
            go.Bar(
                x=df_copy["month_label"],
                y=df_copy["income"],
                name="Income",
                marker_color="#2ca02c",
            )
        )
        fig.add_trace(
            go.Bar(
                x=df_copy["month_label"],
                y=df_copy["expenses"],
                name="Expenses",
                marker_color="#d62728",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_copy["month_label"],
                y=df_copy["net_savings"],
                name="Net Savings",
                line=dict(color="#1f77b4", width=3),
                mode="lines+markers",
            )
        )

    fig.update_layout(
        title="Monthly Cash Flow & Net Savings",
        xaxis_title="Month",
        yaxis_title=f"Amount ({currency})",
        barmode="group",
        hovermode="x unified",
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def plot_spending_by_source(df: pd.DataFrame, currency: str = "INR") -> go.Figure:
    """Bar chart showing spending and transaction count across ingest channels."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Spending by Source Channel (No Data Available)")
        return fig

    fig = px.bar(
        df,
        x="source_type",
        y="total_debit",
        color="source_type",
        title="Expenditure by Transaction Source",
        text_auto=",.2f",
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_layout(
        xaxis_title="Source Channel",
        yaxis_title=f"Total Debits ({currency})",
        template="plotly_white",
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def plot_debit_credit_distribution(df: pd.DataFrame, currency: str = "INR") -> go.Figure:
    """Donut chart showing Debit vs Credit volume distribution."""
    if df.empty or df["total_volume"].sum() == 0:
        fig = go.Figure()
        fig.update_layout(title="Debit vs. Credit Distribution (No Data)")
        return fig

    fig = px.pie(
        df,
        values="total_volume",
        names="direction",
        title="Total Outflow vs. Inflow Volume",
        hole=0.45,
        color="direction",
        color_discrete_map={"DEBIT": "#d62728", "CREDIT": "#2ca02c"},
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate=(
            f"<b>%{{label}}</b><br>Volume: {currency} %{{value:,.2f}}<br>Share: %{{percent}}"
        ),
    )
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def plot_anomaly_timeline(df: pd.DataFrame) -> go.Figure:
    """Timeline stacked bar chart showing normal vs anomalous transactions."""
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(
            go.Bar(
                x=df["transaction_date"],
                y=df["normal_count"],
                name="Normal Transactions",
                marker_color="#2ca02c",
            )
        )
        fig.add_trace(
            go.Bar(
                x=df["transaction_date"],
                y=df["anomalies_count"],
                name="Anomalies",
                marker_color="#d62728",
            )
        )

    fig.update_layout(
        title="Daily Anomaly Occurrence Over Time",
        xaxis_title="Transaction Date",
        yaxis_title="Transaction Count",
        barmode="stack",
        hovermode="x unified",
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def plot_anomaly_distribution(
    df: pd.DataFrame,
    title: str = "Anomalies by Dimension",
    color_scale: str = "Reds",
) -> go.Figure:
    """Horizontal bar chart showing anomaly distribution across a dimension."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (No Anomalies Recorded)")
        return fig

    df_sorted = df.sort_values(by="anomaly_count", ascending=True)
    fig = px.bar(
        df_sorted,
        x="anomaly_count",
        y="label",
        orientation="h",
        title=title,
        text_auto=True,
        color="anomaly_count",
        color_continuous_scale=color_scale,
    )
    fig.update_layout(
        xaxis_title="Number of Anomalies",
        yaxis_title="Dimension",
        template="plotly_white",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def plot_cohort_comparison(stats: dict[str, Any], currency: str = "INR") -> go.Figure:
    """Grouped bar chart comparing normal vs anomalous spending cohorts."""
    cohorts = ["Normal Transactions", "Anomalous Cohort"]
    avg_amounts = [stats.get("normal_avg_amount", 0.0), stats.get("anomalous_avg_amount", 0.0)]
    max_amounts = [stats.get("normal_max_amount", 0.0), stats.get("anomalous_max_amount", 0.0)]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=cohorts,
            y=avg_amounts,
            name=f"Average Amount ({currency})",
            marker_color=["#4575b4", "#d73027"],
            text=[f"{currency} {v:,.2f}" for v in avg_amounts],
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            x=cohorts,
            y=max_amounts,
            name=f"Max Single Amount ({currency})",
            marker_color=["#91bfdb", "#fc8d59"],
            text=[f"{currency} {v:,.2f}" for v in max_amounts],
            textposition="auto",
        )
    )

    fig.update_layout(
        title="Cohort Spending Comparison: Normal vs. Flagged Anomalies",
        yaxis_title=f"Amount ({currency})",
        barmode="group",
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig
