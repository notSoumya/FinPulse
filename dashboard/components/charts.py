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

    # Sort ascending for natural top-down horizontal view
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
        df["month_label"] = pd.to_datetime(df["transaction_month"]).dt.strftime("%b %Y")
        fig.add_trace(
            go.Bar(
                x=df["month_label"],
                y=df["income"],
                name="Income",
                marker_color="#2ca02c",
            )
        )
        fig.add_trace(
            go.Bar(
                x=df["month_label"],
                y=df["expenses"],
                name="Expenses",
                marker_color="#d62728",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["month_label"],
                y=df["net_savings"],
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
