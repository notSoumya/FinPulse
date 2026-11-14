"""
FinPulse Machine Learning — End-to-End Anomaly Training & Scoring Pipeline.

Reads curated transactions from DuckDB warehouse, trains the Isolation Forest model,
scores all transactions with calibrated anomaly metrics and explainability signals,
and persists predictions idempotently back to DuckDB table silver.anomalies.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ml.anomaly_detector import AnomalyDetector
from ml.evaluator import AnomalyEvaluator

logger = logging.getLogger(__name__)


def run_anomaly_pipeline(
    db_path: Path | str | None = None,
    model_dir: Path | str = "models/anomaly_detection",
    contamination: float = 0.08,
) -> dict[str, Any]:
    """
    Execute full anomaly detection lifecycle:
    1. Read transactions from DuckDB.
    2. Fit Isolation Forest and calibrate scores.
    3. Generate explainability signals for each transaction.
    4. Save model artifact.
    5. Sync anomaly table in DuckDB warehouse.
    6. Run evaluation report.
    """
    if db_path is None:
        db_path = Path(os.getenv("FINPULSE_DUCKDB_PATH", "data/warehouse/finpulse.duckdb"))
    else:
        db_path = Path(db_path)

    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB database not found at {db_path}")

    # Read curated transactions from warehouse
    with duckdb.connect(str(db_path)) as con:
        # Check if silver.transactions or stg_transactions exists
        stg_check_sql = (
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name = 'stg_transactions'"
        )
        has_stg = con.execute(stg_check_sql).fetchone()[0] > 0

        if has_stg:
            query = """
                SELECT
                    transaction_id,
                    user_id,
                    amount,
                    currency,
                    direction,
                    transaction_timestamp,
                    merchant_name,
                    source_type
                FROM main.stg_transactions
                ORDER BY transaction_timestamp ASC
            """
        else:
            query = """
                SELECT
                    transaction_id,
                    user_id,
                    amount,
                    currency,
                    direction,
                    transaction_timestamp,
                    coalesce(
                        nullif(trim(merchant_normalized), ''),
                        nullif(trim(merchant_raw), ''),
                        'Unknown'
                    ) as merchant_name,
                    source_type
                FROM silver.transactions
                ORDER BY transaction_timestamp ASC
            """
        df_txns = con.execute(query).df()

    if df_txns.empty:
        logger.warning("No transactions found in %s to train anomaly detector.", db_path)
        return {"status": "SKIPPED", "transactions_scored": 0}

    logger.info("Training Isolation Forest on %d transactions...", len(df_txns))
    detector = AnomalyDetector(contamination=contamination)
    detector.fit(df_txns)

    # Save model artifact
    saved_model_path = detector.save(model_dir)
    logger.info("Saved model artifact to %s", saved_model_path)

    # Score all transactions
    explanations = detector.predict(df_txns)

    # Prepare DataFrame for DuckDB persistence
    records = []
    for exp in explanations:
        records.append(
            {
                "transaction_id": exp.transaction_id,
                "user_id": df_txns.loc[
                    df_txns["transaction_id"] == exp.transaction_id, "user_id"
                ].values[0]
                if exp.transaction_id in df_txns["transaction_id"].values
                else "unknown",
                "anomaly_score": float(exp.anomaly_score),
                "is_anomaly": bool(exp.is_anomaly),
                "severity": exp.severity,
                "primary_reason": exp.primary_reason,
                "contributing_signals": json.dumps(exp.contributing_signals),
                "model_version": exp.model_version,
                "detected_at": exp.detected_at,
            }
        )

    df_anomalies = pd.DataFrame(records)

    # Sync to DuckDB silver.anomalies table
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS silver")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS silver.anomalies (
                transaction_id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                anomaly_score DOUBLE,
                is_anomaly BOOLEAN,
                severity VARCHAR,
                primary_reason VARCHAR,
                contributing_signals VARCHAR,
                model_version VARCHAR,
                detected_at TIMESTAMPTZ
            )
            """
        )
        # Idempotent write via delete + insert
        con.register("df_anomalies_temp", df_anomalies)
        con.execute(
            """
            DELETE FROM silver.anomalies
            WHERE transaction_id IN (SELECT transaction_id FROM df_anomalies_temp)
            """
        )
        con.execute(
            """
            INSERT INTO silver.anomalies
            SELECT
                transaction_id,
                user_id,
                anomaly_score,
                is_anomaly,
                severity,
                primary_reason,
                contributing_signals,
                model_version,
                cast(detected_at as TIMESTAMPTZ)
            FROM df_anomalies_temp
            """
        )
        # Create gold_anomalies view joining stg_transactions with silver.anomalies
        con.execute(
            """
            CREATE OR REPLACE VIEW main.gold_anomalies AS
            SELECT
                t.transaction_id,
                t.user_id,
                t.amount,
                t.currency,
                t.direction,
                t.transaction_timestamp,
                t.transaction_date,
                t.transaction_month,
                t.merchant_name,
                t.source_type,
                case
                    when lower(t.merchant_name) like '%amazon%'
                        or lower(t.merchant_name) like '%flipkart%' then 'Shopping'
                    when lower(t.merchant_name) like '%swiggy%'
                        or lower(t.merchant_name) like '%zomato%'
                        or lower(t.merchant_name) like '%blinkit%'
                        or lower(t.merchant_name) like '%instamart%' then 'Food & Groceries'
                    when lower(t.merchant_name) like '%uber%'
                        or lower(t.merchant_name) like '%ola%'
                        or lower(t.merchant_name) like '%metro%'
                        or lower(t.merchant_name) like '%irctc%' then 'Travel & Commute'
                    when lower(t.merchant_name) like '%salary%' then 'Income'
                    else 'Uncategorized'
                end as spending_category,
                coalesce(a.anomaly_score, 0.0) as anomaly_score,
                coalesce(a.is_anomaly, false) as is_anomaly,
                coalesce(a.severity, 'Normal') as severity,
                coalesce(a.primary_reason, 'Normal spending behavior') as primary_reason,
                coalesce(a.contributing_signals, '[]') as contributing_signals,
                coalesce(a.model_version, 'none') as model_version,
                a.detected_at
            FROM main.stg_transactions t
            LEFT JOIN silver.anomalies a
                ON t.transaction_id = a.transaction_id
            """
        )
        con.unregister("df_anomalies_temp")

    # Run evaluation benchmark
    evaluator = AnomalyEvaluator(detector=detector)
    eval_report = evaluator.generate_full_report(
        df_txns,
        output_file=model_dir / "evaluation_report.json",
    )

    anom_count = int(df_anomalies["is_anomaly"].sum())
    high_count = int((df_anomalies["severity"] == "High").sum())

    logger.info(
        "Anomaly detection pipeline finished: Scored %d transactions, "
        "%d anomalies (%d High severity).",
        len(df_anomalies),
        anom_count,
        high_count,
    )

    return {
        "status": "SUCCESS",
        "transactions_scored": len(df_anomalies),
        "anomalies_detected": anom_count,
        "high_severity_count": high_count,
        "evaluation": eval_report,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run_anomaly_pipeline()
