import json

import streamlit as st

from dashboard.components.charts import (
    plot_anomaly_distribution,
    plot_anomaly_timeline,
    plot_cohort_comparison,
)
from dashboard.components.sidebar import render_sidebar
from dashboard.database import is_database_available
from dashboard.metrics import format_currency
from dashboard.queries import (
    get_anomaly_distributions,
    get_anomaly_investigation_records,
    get_anomaly_kpis,
    get_anomaly_normal_comparison,
    get_anomaly_timeline,
)

st.set_page_config(
    page_title="Anomaly Detection | FinPulse",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ Financial Anomaly Detection & Investigation")
st.markdown(
    """
    Genuine machine learning anomaly detection powered by **Isolation Forest** with multidimensional
    behavioral feature engineering, calibrated scoring, and explainability reasoning.
    """
)

if not is_database_available():
    st.error("Warehouse database not available. Please run the pipeline first.")
    st.stop()

filters = render_sidebar()
currency = filters["currency"]

# Fetch Anomaly KPIs
kpis = get_anomaly_kpis(
    user_id=filters["user_id"],
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    currency=currency,
)

# Row 1: KPI Cards
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    st.metric(
        label="Total Evaluated Transactions",
        value=f"{kpis['total_evaluated']:,}",
    )

with kpi_col2:
    st.metric(
        label="Total Anomalies Detected",
        value=f"{kpis['total_anomalies']:,}",
        delta=f"{kpis['anomaly_pct']:.1f}% rate",
        delta_color="inverse",
    )

with kpi_col3:
    st.metric(
        label="High-Severity Anomalies",
        value=f"{kpis['high_severity_count']:,}",
        delta="Requires Priority Audit" if kpis["high_severity_count"] > 0 else "None",
        delta_color="inverse",
    )

with kpi_col4:
    st.metric(
        label="Medium / Low Anomalies",
        value=f"{kpis['medium_severity_count'] + kpis['low_severity_count']:,}",
    )

st.markdown("---")

# Row 2: Anomaly Trends over Time & Cohort Comparison
st.subheader("1. Anomaly Trajectory & Cohort Comparison")
trend_col1, trend_col2 = st.columns([1.4, 1])

with trend_col1:
    df_timeline = get_anomaly_timeline(user_id=filters["user_id"], currency=currency)
    fig_timeline = plot_anomaly_timeline(df_timeline)
    st.plotly_chart(fig_timeline, use_container_width=True)

with trend_col2:
    cohort_stats = get_anomaly_normal_comparison(user_id=filters["user_id"], currency=currency)
    fig_cohort = plot_cohort_comparison(cohort_stats, currency=currency)
    st.plotly_chart(fig_cohort, use_container_width=True)

# Row 3: Multidimensional Anomaly Distributions
st.markdown("---")
st.subheader("2. Multidimensional Anomaly Distributions")
dist_col1, dist_col2, dist_col3 = st.columns(3)

with dist_col1:
    df_cat_anom = get_anomaly_distributions(
        dimension="category", user_id=filters["user_id"], currency=currency
    )
    fig_cat_anom = plot_anomaly_distribution(
        df_cat_anom, title="Anomalies by Spending Category", color_scale="Reds"
    )
    st.plotly_chart(fig_cat_anom, use_container_width=True)

with dist_col2:
    df_merch_anom = get_anomaly_distributions(
        dimension="merchant", user_id=filters["user_id"], currency=currency
    )
    fig_merch_anom = plot_anomaly_distribution(
        df_merch_anom, title="Top Merchants with Anomalies", color_scale="Oranges"
    )
    st.plotly_chart(fig_merch_anom, use_container_width=True)

with dist_col3:
    df_src_anom = get_anomaly_distributions(
        dimension="source", user_id=filters["user_id"], currency=currency
    )
    fig_src_anom = plot_anomaly_distribution(
        df_src_anom, title="Anomalies by Transaction Source", color_scale="Purples"
    )
    st.plotly_chart(fig_src_anom, use_container_width=True)

# Row 4: Dedicated Anomaly Investigation Table
st.markdown("---")
st.subheader("3. Anomaly Investigation & Drill-Down Inspector")

inv_col1, inv_col2, inv_col3 = st.columns([1, 1, 1])
with inv_col1:
    severity_filter = st.selectbox(
        "Filter by Severity", options=["All", "High", "Medium", "Low"], index=0
    )
with inv_col2:
    inv_category = st.selectbox(
        "Filter by Category",
        options=[
            "All",
            "Shopping",
            "Food & Groceries",
            "Travel & Commute",
            "Income",
            "Uncategorized",
        ],
        index=0,
    )
with inv_col3:
    table_limit = st.selectbox("Display Limit", options=[10, 25, 50], index=1)

df_inv, total_anom_matches = get_anomaly_investigation_records(
    user_id=filters["user_id"],
    severity=severity_filter,
    category=inv_category,
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    currency=currency,
    limit=table_limit,
)

st.caption(f"Showing {len(df_inv)} of {total_anom_matches} matching anomalies")

if not df_inv.empty:
    display_inv = df_inv.copy()
    display_inv["amount"] = display_inv["amount"].apply(lambda v: format_currency(v, currency))
    display_inv["anomaly_score"] = display_inv["anomaly_score"].apply(lambda s: f"{float(s):.3f}")

    sev_icons = {"High": "🔴 High", "Medium": "🟠 Medium", "Low": "🟡 Low", "Normal": "🟢 Normal"}
    display_inv["severity"] = display_inv["severity"].apply(lambda s: sev_icons.get(s, s))

    show_cols = [
        "transaction_date",
        "merchant_name",
        "amount",
        "user_id",
        "category",
        "anomaly_score",
        "severity",
        "primary_reason",
    ]
    rename_inv = {
        "transaction_date": "Date",
        "merchant_name": "Merchant",
        "amount": "Amount",
        "user_id": "User",
        "category": "Category",
        "anomaly_score": "Score",
        "severity": "Severity",
        "primary_reason": "Contributing Behavioral Reason",
    }
    st.dataframe(
        display_inv[show_cols].rename(columns=rename_inv),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### 🔬 Detailed Transaction Drill-Down")
    inv_options = [
        f"[{r['severity']}] {r['transaction_date']} | "
        f"{r['merchant_name']} | {r['amount']} (Score: {r['anomaly_score']})"
        for _, r in display_inv.iterrows()
    ]
    selected_inv_idx = st.selectbox(
        "Select Anomaly Record to Inspect Explanation & Signals",
        options=range(len(inv_options)),
        format_func=lambda i: inv_options[i],
    )
    chosen_rec = df_inv.iloc[selected_inv_idx]

    detail_c1, detail_c2 = st.columns([1, 1.5])
    with detail_c1:
        st.markdown(f"**Transaction ID:** `{chosen_rec['transaction_id']}`")
        st.markdown(f"**User ID:** `{chosen_rec['user_id']}`")
        st.markdown(f"**Date:** {chosen_rec['transaction_date']}")
        st.markdown(f"**Merchant:** **{chosen_rec['merchant_name']}**")
        st.markdown(f"**Amount:** {format_currency(chosen_rec['amount'], currency)}")
        st.markdown(f"**Direction:** `{chosen_rec['direction']}`")
        st.markdown(f"**Channel Source:** `{chosen_rec['source_type']}`")
        st.markdown(f"**Anomaly Score:** `{chosen_rec['anomaly_score']}`")
        st.markdown(f"**Severity Level:** `{chosen_rec['severity']}`")

    with detail_c2:
        st.markdown("##### 📌 Behavioral Explainability Signals")
        st.info(f"**Primary Reason:** {chosen_rec['primary_reason']}")
        signals_raw = chosen_rec.get("contributing_signals", "[]")
        try:
            signals_list = json.loads(signals_raw) if isinstance(signals_raw, str) else signals_raw
        except Exception:
            signals_list = [str(signals_raw)]

        st.markdown("**Contributing Context Signals Identified by Model:**")
        for sig in signals_list:
            st.markdown(f"- ⚠️ {sig}")

        ver = chosen_rec.get("model_version", "v1.0")
        st.caption(f"Scored by Isolation Forest Engine • Model Version: `{ver}`")
else:
    st.success("🎉 No anomalies detected matching the active filters!")
