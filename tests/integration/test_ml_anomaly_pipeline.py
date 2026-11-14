"""Integration tests for the ML anomaly pipeline and DuckDB synchronization."""

import duckdb
import pytest

from ml.pipeline import run_anomaly_pipeline


@pytest.fixture
def warehouse_with_transactions(tmp_path):
    """Setup a DuckDB database populated with staging transactions."""
    db_file = tmp_path / "test_warehouse.duckdb"
    with duckdb.connect(str(db_file)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS silver")
        con.execute("CREATE SCHEMA IF NOT EXISTS main")
        con.execute(
            """
            CREATE TABLE main.stg_transactions (
                transaction_id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                amount DECIMAL(18, 2),
                currency VARCHAR,
                direction VARCHAR,
                transaction_timestamp TIMESTAMPTZ,
                transaction_date DATE,
                transaction_month DATE,
                merchant_name VARCHAR,
                source_type VARCHAR
            )
            """
        )

        # Insert 30 baseline transactions and 2 outliers
        rows = []
        for i in range(30):
            rows.append(
                f"('tx_{i}', 'user_1', 350.00, 'INR', 'DEBIT', "
                "'2026-10-01 12:00:00+00', '2026-10-01', '2026-10-01', 'Swiggy', 'UPI_CSV')"
            )
        rows.append(
            "('tx_outlier_1', 'user_1', 75000.00, 'INR', 'DEBIT', "
            "'2026-10-15 03:00:00+00', '2026-10-15', '2026-10-01', 'Rare Merchant', 'CARD_PDF')"
        )
        rows.append(
            "('tx_outlier_2', 'user_1', 99000.00, 'INR', 'DEBIT', "
            "'2026-10-20 02:00:00+00', '2026-10-20', '2026-10-01', 'Crypto Vault', 'MANUAL')"
        )

        con.execute(f"INSERT INTO main.stg_transactions VALUES {', '.join(rows)}")

    return db_file


def test_run_anomaly_pipeline_end_to_end(warehouse_with_transactions, tmp_path):
    model_dir = tmp_path / "models"
    res = run_anomaly_pipeline(
        db_path=warehouse_with_transactions,
        model_dir=model_dir,
        contamination=0.10,
    )

    assert res["status"] == "SUCCESS"
    assert res["transactions_scored"] == 32
    assert res["anomalies_detected"] >= 2
    assert res["high_severity_count"] >= 1

    # Verify DuckDB silver.anomalies
    with duckdb.connect(str(warehouse_with_transactions)) as con:
        table_count = con.execute("SELECT count(*) FROM silver.anomalies").fetchone()[0]
        assert table_count == 32

        # Verify outlier is marked
        check_sql = (
            "SELECT is_anomaly, severity, primary_reason "
            "FROM silver.anomalies WHERE transaction_id = 'tx_outlier_2'"
        )
        outlier_res = con.execute(check_sql).fetchone()
        assert outlier_res[0] is True
        assert outlier_res[1] in ["Medium", "High"]

        # Verify gold_anomalies view
        view_count = con.execute("SELECT count(*) FROM main.gold_anomalies").fetchone()[0]
        assert view_count == 32


def test_anomaly_pipeline_idempotency(warehouse_with_transactions, tmp_path):
    model_dir = tmp_path / "models"

    # Run once
    res1 = run_anomaly_pipeline(warehouse_with_transactions, model_dir=model_dir)
    assert res1["transactions_scored"] == 32

    # Run twice
    res2 = run_anomaly_pipeline(warehouse_with_transactions, model_dir=model_dir)
    assert res2["transactions_scored"] == 32

    # Exactly 32 rows should exist, no duplicate key errors
    with duckdb.connect(str(warehouse_with_transactions)) as con:
        total = con.execute("SELECT count(*) FROM silver.anomalies").fetchone()[0]
        assert total == 32
