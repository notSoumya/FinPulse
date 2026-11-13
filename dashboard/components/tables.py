import pandas as pd
import streamlit as st


def render_transactions_table(df: pd.DataFrame, currency: str = "INR"):
    """Format and display transactions DataFrame with clean styling."""
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

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )
