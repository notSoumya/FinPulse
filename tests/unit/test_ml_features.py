"""Unit tests for ML feature engineering."""

from datetime import UTC, datetime

import pandas as pd

from ml.features import TransactionFeatureEngineer, infer_category


def test_infer_category():
    assert infer_category("Amazon India", "DEBIT") == "Shopping"
    assert infer_category("Swiggy Delivery", "DEBIT") == "Food & Groceries"
    assert infer_category("Uber Trip", "DEBIT") == "Travel & Commute"
    assert infer_category("Monthly Salary Credit", "CREDIT") == "Income"
    assert infer_category("Random Merchant", "DEBIT") == "Uncategorized"


def test_empty_dataframe_features():
    engineer = TransactionFeatureEngineer()
    res = engineer.extract_features(pd.DataFrame(), is_training=True)
    assert res.empty


def test_single_user_feature_extraction():
    data = [
        {
            "transaction_id": "tx1",
            "user_id": "user_a",
            "amount": 100.0,
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
            "merchant_name": "Amazon",
            "source_type": "UPI_CSV",
        },
        {
            "transaction_id": "tx2",
            "user_id": "user_a",
            "amount": 250.0,
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 9, 2, 14, 0, tzinfo=UTC),
            "merchant_name": "Amazon",
            "source_type": "UPI_CSV",
        },
        {
            "transaction_id": "tx3",
            "user_id": "user_a",
            "amount": 5000.0,
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 9, 3, 23, 30, tzinfo=UTC),
            "merchant_name": "New Electronics",
            "source_type": "CARD_PDF",
        },
    ]
    df = pd.DataFrame(data)
    engineer = TransactionFeatureEngineer()
    features = engineer.extract_features(df, is_training=True)

    assert len(features) == 3
    assert "log_amount" in features.columns
    assert "user_amount_zscore" in features.columns
    assert "is_new_merchant" in features.columns

    # tx1 is first transaction: prior count should be 0, is_new_merchant is 1
    row1 = features.iloc[0]
    assert row1["user_tx_prior_count"] == 0
    assert row1["is_new_merchant"] == 1

    # tx2: Amazon seen before, is_new_merchant is 0
    row2 = features.iloc[1]
    assert row2["user_tx_prior_count"] == 1
    assert row2["is_new_merchant"] == 0

    # tx3: amount 5000 is much higher, zscore should be positive
    row3 = features.iloc[2]
    assert row3["user_tx_prior_count"] == 2
    assert row3["user_amount_zscore"] > 0
    assert row3["hour"] == 23


def test_multi_user_isolation():
    """Ensure user 1 history does not bleed into user 2 calculations."""
    data = [
        {
            "transaction_id": "u1_tx1",
            "user_id": "user_1",
            "amount": 50000.0,
            "direction": "CREDIT",
            "transaction_timestamp": datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
            "merchant_name": "Salary",
            "source_type": "BANK_SMS",
        },
        {
            "transaction_id": "u2_tx1",
            "user_id": "user_2",
            "amount": 100.0,
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 9, 1, 10, 30, tzinfo=UTC),
            "merchant_name": "Swiggy",
            "source_type": "UPI_CSV",
        },
    ]
    df = pd.DataFrame(data)
    engineer = TransactionFeatureEngineer()
    features = engineer.extract_features(df, is_training=True)

    u1_row = features[features["user_id"] == "user_1"].iloc[0]
    u2_row = features[features["user_id"] == "user_2"].iloc[0]

    # Both are first transactions for their respective users
    assert u1_row["user_tx_prior_count"] == 0
    assert u2_row["user_tx_prior_count"] == 0
    assert u2_row["user_expanding_mean"] == 100.0
