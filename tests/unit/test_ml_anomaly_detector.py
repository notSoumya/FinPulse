"""Unit tests for Isolation Forest anomaly detection and explainability."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from ml.anomaly_detector import AnomalyDetector


@pytest.fixture
def sample_transactions():
    """Generate 40 typical transactions and 2 intentional anomalies."""
    records = []
    base_ts = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)

    # 40 normal transactions (small to moderate grocery/commute/shopping)
    for i in range(40):
        records.append(
            {
                "transaction_id": f"tx_normal_{i}",
                "user_id": "test_user",
                "amount": 250.0 + (i % 5) * 50.0,
                "currency": "INR",
                "direction": "DEBIT",
                "transaction_timestamp": base_ts + timedelta(days=i, hours=2),
                "merchant_name": "Swiggy" if i % 2 == 0 else "Uber",
                "source_type": "UPI_CSV",
            }
        )

    # 2 extreme anomalies
    records.append(
        {
            "transaction_id": "tx_anomaly_extreme_1",
            "user_id": "test_user",
            "amount": 85000.0,
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": base_ts + timedelta(days=41, hours=17),  # 3 AM off-hours
            "merchant_name": "Unknown Luxury Jeweler",
            "source_type": "CARD_PDF",
        }
    )
    records.append(
        {
            "transaction_id": "tx_anomaly_extreme_2",
            "user_id": "test_user",
            "amount": 95000.0,
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": base_ts + timedelta(days=42, hours=18),
            "merchant_name": "Foreign Crypto Exchange",
            "source_type": "MANUAL",
        }
    )
    return pd.DataFrame(records)


def test_detector_fit_and_predict(sample_transactions):
    detector = AnomalyDetector(contamination=0.10)
    detector.fit(sample_transactions)
    assert detector.is_fitted

    explanations = detector.predict(sample_transactions)
    assert len(explanations) == len(sample_transactions)

    # Find the extreme transaction
    anom_rec = [e for e in explanations if e.transaction_id == "tx_anomaly_extreme_1"][0]
    assert anom_rec.is_anomaly
    assert anom_rec.severity in ["Medium", "High"]
    assert anom_rec.anomaly_score > 0.65
    assert len(anom_rec.contributing_signals) > 0
    assert "deviates" in anom_rec.primary_reason or "deviates" in " ".join(
        anom_rec.contributing_signals
    )


def test_detector_save_and_load(sample_transactions, tmp_path):
    detector = AnomalyDetector(contamination=0.10)
    detector.fit(sample_transactions)

    model_dir = tmp_path / "models"
    saved_path = detector.save(model_dir)
    assert saved_path.exists()

    loaded_detector = AnomalyDetector.load(saved_path)
    assert loaded_detector.is_fitted

    preds_original = detector.predict(sample_transactions[:5])
    preds_loaded = loaded_detector.predict(sample_transactions[:5])

    for p_orig, p_load in zip(preds_original, preds_loaded):
        assert p_orig.transaction_id == p_load.transaction_id
        assert p_orig.anomaly_score == p_load.anomaly_score
        assert p_orig.is_anomaly == p_load.is_anomaly
        assert p_orig.severity == p_load.severity


def test_empty_dataset_raises():
    detector = AnomalyDetector()
    with pytest.raises(ValueError):
        detector.fit(pd.DataFrame())
