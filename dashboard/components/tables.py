import pandas as pd
import streamlit as st


def render_transactions_table(df: pd.DataFrame, currency: str = "INR"):
    """Format and display transactions DataFrame with clean styling and anomaly badges."""
    if df.empty:
        st.info("No transactions found matching the selected filters.")
        return

    display_df = df.copy()

    # Format monetary amounts
    if "amount" in display_df.columns:
        display_df["amount"] = display_df["amount"].apply(
            lambda v: f"{currency} {float(v):,.2f}" if pd.notnull(v) else "-"
        )

    # Format dates
    if "transaction_date" in display_df.columns:
        display_df["transaction_date"] = pd.to_datetime(display_df["transaction_date"]).dt.strftime(
            "%Y-%m-%d"
        )

    # Format anomaly indicators
    if "is_anomaly" in display_df.columns:
        display_df["is_anomaly"] = display_df["is_anomaly"].apply(
            lambda v: "🚨 Flagged" if v else "✅ Normal"
        )

    if "anomaly_score" in display_df.columns:
        display_df["anomaly_score"] = display_df["anomaly_score"].apply(
            lambda s: f"{float(s):.3f}" if pd.notnull(s) else "0.000"
        )

    # Format severity
    if "severity" in display_df.columns:
        sev_icons = {
            "High": "🔴 High",
            "Medium": "🟠 Medium",
            "Low": "🟡 Low",
            "Normal": "🟢 Normal",
        }
        display_df["severity"] = display_df["severity"].apply(lambda s: sev_icons.get(s, s))

    rename_map = {
        "transaction_id": "Transaction ID",
        "transaction_date": "Date",
        "merchant_name": "Merchant",
        "amount": "Amount",
        "direction": "Direction",
        "category": "Category",
        "source_type": "Source",
        "is_anomaly": "Status",
        "anomaly_score": "Score",
        "severity": "Severity",
    }
    cols_to_show = [c for c in rename_map.keys() if c in display_df.columns]
    renamed_df = display_df[cols_to_show].rename(columns=rename_map)

    st.dataframe(
        renamed_df,
        use_container_width=True,
        hide_index=True,
    )
