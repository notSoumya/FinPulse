"""
End-to-End Synthetic Pipeline Execution & Independent Analytical Validation.

Executes:
1. Source Ingestion (UPI, Card, SMS, Manual) -> Bronze storage
2. Silver Pipeline (validation, cleaning, normalization, dedup, Delta Lake, quarantine)
3. Warehouse Sync (Delta Lake -> DuckDB)
4. dbt Transformations & Quality Tests (Staging, Intermediate, Gold marts)
5. Independent calculation of financial analytics (no reuse of dbt SQL or dashboard queries)
6. Automated reconciliation between Expected and Actual outputs
7. Saves data/synthetic/reports/analytics_reconciliation.json
"""

import json
import sys, os
# Ensure repository root is on PYTHONPATH for top-level package imports
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Also add the src directory where the finpulse package lives
src_root = os.path.abspath(os.path.join(repo_root, "src"))
if src_root not in sys.path:
    sys.path.append(src_root)
if repo_root not in sys.path:
    sys.path.append(repo_root)
import logging
import os
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
from dbt.cli.main import dbtRunner

from finpulse.bronze.storage import BronzeStorage
from finpulse.common.models import Transaction
from finpulse.ingestion.parsers.card_pdf_parser import parse_card_pdf
from finpulse.ingestion.parsers.manual_parser import parse_manual
from finpulse.ingestion.parsers.sms_parser import parse_bank_sms
from finpulse.ingestion.parsers.upi_parser import parse_upi_csv
from finpulse.processing.bronze_reader import BronzeReader
from finpulse.processing.checkpoint import CheckpointManager
from finpulse.processing.merchant_normalizer import MerchantNormalizer
from finpulse.processing.quarantine import QuarantineManager
from finpulse.processing.silver_pipeline import SilverPipeline
from finpulse.silver.writer import SilverWriter
from finpulse.warehouse.loader import WarehouseLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def clean_synthetic_env(base_dir: Path):
    """Clean isolated synthetic lake and warehouse folders before run."""
    for sub in ["bronze", "silver", "checkpoints", "quarantine", "warehouse"]:
        p = base_dir / sub
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()


def run_synthetic_pipeline_and_validate(base_dir_str: str = "data/synthetic") -> dict:
    base_dir = Path(base_dir_str)
    manifest_file = base_dir / "manifest.json"
    with open(manifest_file, encoding="utf-8") as f:
        manifest = json.load(f)

    # 0. Clean isolated directories
    clean_synthetic_env(base_dir)

    bronze_dir = base_dir / "bronze"
    silver_dir = base_dir / "silver" / "transactions"
    checkpoint_file = base_dir / "checkpoints" / "silver_checkpoint.json"
    quarantine_dir = base_dir / "quarantine" / "rejected_transactions"
    warehouse_db = base_dir / "warehouse" / "finpulse_synthetic.duckdb"

    # Set env var so dbt connects to synthetic duckdb
    os.environ["FINPULSE_DUCKDB_PATH"] = str(warehouse_db.resolve())

    bronze_storage = BronzeStorage(bronze_dir)
    primary_user = manifest["primary_user"]

    logger.info("==================================================")
    logger.info("STAGE 1 & 2: Ingestion & Bronze Storage")
    logger.info("==================================================")

    all_ingested_txs: list[Transaction] = []

    # 1. UPI CSV Ingestion
    upi_txs = parse_upi_csv(manifest["files"]["upi_csv"], user_id=primary_user)
    # The generator placed some transactions for secondary user in the same CSV
    # Re-assign user if designated in original raw
    with open(manifest["files"]["upi_csv"], encoding="utf-8") as f:
        lines = f.readlines()[1:]
        for i, line in enumerate(lines):
            if "synthetic_user_2" in line or "U2" in line:
                upi_txs[i].user_id = manifest["secondary_user"]

    all_ingested_txs.extend(upi_txs)
    for tx in upi_txs:
        bronze_storage.write_event(
            {
                "event_id": f"evt_{tx.transaction_id}",
                "event_timestamp": tx.transaction_timestamp.isoformat(),
                "schema_version": "1.0",
                "event_type": "TRANSACTION_CREATED",
                "payload": tx.model_dump(mode="json"),
            }
        )

    # 2. Card PDF Ingestion
    card_txs = parse_card_pdf(manifest["files"]["card_pdf"], user_id=primary_user)
    # Handle secondary user for card transactions
    for tx in card_txs:
        # In card statement generator, last 3 transactions were secondary user
        if tx.amount in [
            Decimal("1850.00"),
            Decimal("620.00"),
            Decimal("410.00"),
        ] and tx.transaction_timestamp.month in [10, 11]:
            # Assign user_2
            tx.user_id = manifest["secondary_user"]

    all_ingested_txs.extend(card_txs)
    for tx in card_txs:
        bronze_storage.write_event(
            {
                "event_id": f"evt_{tx.transaction_id}",
                "event_timestamp": tx.transaction_timestamp.isoformat(),
                "schema_version": "1.0",
                "event_type": "TRANSACTION_CREATED",
                "payload": tx.model_dump(mode="json"),
            }
        )

    # 3. Bank SMS Ingestion
    with open(manifest["files"]["bank_sms_json"], encoding="utf-8") as f:
        sms_raw = json.load(f)
    sms_txs = []
    for r in sms_raw:
        ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
        tx = parse_bank_sms(r["message"], r["user_id"], ts, r.get("reference_id"))
        sms_txs.append(tx)
    all_ingested_txs.extend(sms_txs)
    for tx in sms_txs:
        bronze_storage.write_event(
            {
                "event_id": f"evt_{tx.transaction_id}",
                "event_timestamp": tx.transaction_timestamp.isoformat(),
                "schema_version": "1.0",
                "event_type": "TRANSACTION_CREATED",
                "payload": tx.model_dump(mode="json"),
            }
        )

    # 4. Manual Ingestion
    with open(manifest["files"]["manual_json"], encoding="utf-8") as f:
        man_raw = json.load(f)
    man_txs = [parse_manual(r) for r in man_raw]
    all_ingested_txs.extend(man_txs)
    for tx in man_txs:
        bronze_storage.write_event(
            {
                "event_id": f"evt_{tx.transaction_id}",
                "event_timestamp": tx.transaction_timestamp.isoformat(),
                "schema_version": "1.0",
                "event_type": "TRANSACTION_CREATED",
                "payload": tx.model_dump(mode="json"),
            }
        )

    # 5. Inject 2 intentional malformed / invalid Bronze records to test quarantine
    bronze_storage.write_event(
        {
            "event_id": "evt_invalid_malformed_1",
            "event_timestamp": datetime.now(UTC).isoformat(),
            "schema_version": "1.0",
            "event_type": "TRANSACTION_CREATED",
            "payload": {
                "source_type": "MANUAL",
                "invalid_key": "missing required fields",
            },
        }
    )
    bronze_storage.write_event(
        {
            "event_id": "evt_invalid_amount_2",
            "event_timestamp": datetime.now(UTC).isoformat(),
            "schema_version": "1.0",
            "event_type": "TRANSACTION_CREATED",
            "payload": {
                "source_type": "MANUAL",
                "transaction_id": "tx_bad_amount",
                "user_id": primary_user,
                "amount": -50.0,
                "currency": "INR",
                "direction": "DEBIT",
                "transaction_timestamp": "2026-09-01T12:00:00Z",
            },
        }
    )

    # Also inject 1 duplicate event into bronze to test event deduplication
    dup_tx = upi_txs[0]
    bronze_storage.write_event(
        {
            "event_id": f"evt_{dup_tx.transaction_id}",
            "event_timestamp": dup_tx.transaction_timestamp.isoformat(),
            "schema_version": "1.0",
            "event_type": "TRANSACTION_CREATED",
            "payload": dup_tx.model_dump(mode="json"),
        }
    )

    logger.info("Total source records prepared: %d", len(all_ingested_txs))

    logger.info("==================================================")
    logger.info("STAGE 3: Silver Transformation & Delta Lake")
    logger.info("==================================================")

    bronze_reader = BronzeReader(bronze_dir)
    quarantine_manager = QuarantineManager(quarantine_dir)
    silver_writer = SilverWriter(silver_dir)
    checkpoint_manager = CheckpointManager(checkpoint_file)
    merchant_normalizer = MerchantNormalizer("config/merchant_mapping.json")

    silver_pipeline = SilverPipeline(
        bronze_reader=bronze_reader,
        merchant_normalizer=merchant_normalizer,
        quarantine_manager=quarantine_manager,
        silver_writer=silver_writer,
        checkpoint_manager=checkpoint_manager,
    )

    silver_stats = silver_pipeline.run()
    logger.info("Silver pipeline execution stats: %s", silver_stats)

    # Verify checkpoint idempotency: running pipeline a second time should write 0 new records
    second_run_stats = silver_pipeline.run()
    logger.info("Silver idempotency second run stats: %s", second_run_stats)
    assert second_run_stats["transactions_written"] == 0, (
        "Idempotency failure: second run wrote rows!"
    )

    logger.info("==================================================")
    logger.info("STAGE 4: DuckDB Warehouse Synchronization")
    logger.info("==================================================")

    loader = WarehouseLoader(silver_path=silver_dir, db_path=warehouse_db)
    synced_rows = loader.sync()
    logger.info("DuckDB sync completed: %d rows synced into silver.transactions.", synced_rows)

    logger.info("==================================================")
    logger.info("STAGE 5: dbt Transformations & Data Tests")
    logger.info("==================================================")

    dbt = dbtRunner()
    run_res = dbt.invoke(["run", "--project-dir", "dbt", "--profiles-dir", "dbt"])
    assert run_res.success, f"dbt run failed: {run_res.exception}"
    logger.info("dbt models compiled and executed: %d models passed.", len(run_res.result))

    test_res = dbt.invoke(["test", "--project-dir", "dbt", "--profiles-dir", "dbt"])
    assert test_res.success, f"dbt data tests failed: {test_res.exception}"
    logger.info("dbt tests passed: %d tests passed.", len(test_res.result))

    logger.info("==================================================")
    logger.info("STAGE 5B: ML Anomaly Detection Training & Scoring")
    logger.info("==================================================")

    from ml.pipeline import run_anomaly_pipeline

    ml_res = run_anomaly_pipeline(warehouse_db, model_dir=base_dir / "models" / "anomaly_detection")
    logger.info(
        "ML anomaly pipeline executed: %d scored, %d anomalies detected (%d high severity).",
        ml_res["transactions_scored"],
        ml_res["anomalies_detected"],
        ml_res["high_severity_count"],
    )

    logger.info("==================================================")
    logger.info("STAGE 6: Independent Financial Analytics Calculation")
    logger.info("==================================================")

    # Independent calculations directly from the unique cleaned input records for primary_user
    # 1. Deduplicate unique transactions for primary_user
    seen_ids = set()
    primary_clean_txs: list[Transaction] = []
    normalizer = MerchantNormalizer("config/merchant_mapping.json")

    for tx in all_ingested_txs:
        if tx.user_id != primary_user:
            continue
        if tx.transaction_id in seen_ids:
            continue
        seen_ids.add(tx.transaction_id)
        # Apply normalization independently
        normalized_merchant = normalizer.normalize(tx.merchant_raw)
        tx_copy = tx.model_copy(update={"merchant_normalized": normalized_merchant})
        primary_clean_txs.append(tx_copy)

    total_valid_txs = len(primary_clean_txs)
    total_income = Decimal("0.00")
    total_expenses = Decimal("0.00")

    monthly_stats = defaultdict(
        lambda: {"income": Decimal("0.00"), "expenses": Decimal("0.00"), "count": 0}
    )
    category_stats = defaultdict(lambda: {"spent": Decimal("0.00"), "count": 0})
    merchant_stats = defaultdict(lambda: {"spent": Decimal("0.00"), "count": 0})
    source_stats = defaultdict(int)

    for tx in primary_clean_txs:
        source_stats[tx.source_type] += 1
        m_key = tx.transaction_timestamp.strftime("%Y-%m-01")

        m_name = (tx.merchant_normalized or tx.merchant_raw or "Unknown").strip()

        if tx.direction == "CREDIT":
            total_income += tx.amount
            monthly_stats[m_key]["income"] += tx.amount
        else:
            total_expenses += tx.amount
            monthly_stats[m_key]["expenses"] += tx.amount
            merchant_stats[m_name]["spent"] += tx.amount
            merchant_stats[m_name]["count"] += 1

            # Independent categorization rule matching dbt logic
            m_lower = m_name.lower()
            if "amazon" in m_lower or "flipkart" in m_lower:
                cat = "Shopping"
            elif any(k in m_lower for k in ["swiggy", "zomato", "blinkit", "instamart"]):
                cat = "Food & Groceries"
            elif any(k in m_lower for k in ["uber", "ola", "metro", "irctc"]):
                cat = "Travel & Commute"
            elif "salary" in m_lower:
                cat = "Income"
            else:
                cat = "Uncategorized"

            category_stats[cat]["spent"] += tx.amount
            category_stats[cat]["count"] += 1

        monthly_stats[m_key]["count"] += 1

    net_cash_flow = total_income - total_expenses
    savings_rate = (
        round((net_cash_flow / total_income * 100), 2) if total_income > 0 else Decimal("0.00")
    )

    expected_analytics = {
        "user_id": primary_user,
        "total_transactions": total_valid_txs,
        "total_income": float(total_income),
        "total_expenses": float(total_expenses),
        "net_cash_flow": float(net_cash_flow),
        "savings_rate_pct": float(savings_rate),
        "source_counts": dict(source_stats),
        "monthly": {
            k: {"income": float(v["income"]), "expenses": float(v["expenses"]), "count": v["count"]}
            for k, v in sorted(monthly_stats.items())
        },
        "categories": {
            k: {"spent": float(v["spent"]), "count": v["count"]}
            for k, v in sorted(category_stats.items())
        },
        "top_merchants": {
            k: float(v["spent"])
            for k, v in sorted(
                merchant_stats.items(), key=lambda item: item[1]["spent"], reverse=True
            )[:5]
        },
    }

    logger.info("Independent expected results computed successfully.")

    logger.info("==================================================")
    logger.info("STAGE 7: Reconciling against DuckDB Gold Marts")
    logger.info("==================================================")

    reconciliation_items = []

    with duckdb.connect(str(warehouse_db)) as con:
        # 1. Total Transactions in Silver & Staging
        db_count = con.execute(
            "SELECT count(*) FROM silver.transactions WHERE user_id = ?", [primary_user]
        ).fetchone()[0]
        reconciliation_items.append(
            {
                "metric": "total_transactions",
                "expected": total_valid_txs,
                "actual": db_count,
                "difference": db_count - total_valid_txs,
                "status": "PASS" if db_count == total_valid_txs else "FAIL",
            }
        )

        # 2. Total Income & Expenses via Cashflow Mart
        cf_rows = con.execute(
            """
            SELECT direction, sum(total_volume)
            FROM main.gold_cashflow_summary
            WHERE user_id = ?
            GROUP BY direction
            """,
            [primary_user],
        ).fetchall()
        actual_cf = {row[0]: float(row[1]) for row in cf_rows}

        reconciliation_items.append(
            {
                "metric": "total_income",
                "expected": float(total_income),
                "actual": actual_cf.get("CREDIT", 0.0),
                "difference": actual_cf.get("CREDIT", 0.0) - float(total_income),
                "status": "PASS"
                if abs(actual_cf.get("CREDIT", 0.0) - float(total_income)) < 0.01
                else "FAIL",
            }
        )

        reconciliation_items.append(
            {
                "metric": "total_expenses",
                "expected": float(total_expenses),
                "actual": actual_cf.get("DEBIT", 0.0),
                "difference": actual_cf.get("DEBIT", 0.0) - float(total_expenses),
                "status": "PASS"
                if abs(actual_cf.get("DEBIT", 0.0) - float(total_expenses)) < 0.01
                else "FAIL",
            }
        )

        # 3. Monthly Spending Mart Verification
        monthly_rows = con.execute(
            """
            SELECT
                strftime(transaction_month, '%Y-%m-01') as m,
                monthly_income,
                monthly_expenses,
                net_savings,
                savings_rate_pct,
                total_transactions
            FROM main.gold_monthly_spending
            WHERE user_id = ?
            ORDER BY m
            """,
            [primary_user],
        ).fetchall()

        for row in monthly_rows:
            m_str, m_inc, m_exp, m_net, m_rate, m_cnt = row
            exp_m = expected_analytics["monthly"].get(
                m_str, {"income": 0.0, "expenses": 0.0, "count": 0}
            )
            reconciliation_items.append(
                {
                    "metric": f"monthly_expenses_{m_str}",
                    "expected": exp_m["expenses"],
                    "actual": float(m_exp),
                    "difference": float(m_exp) - exp_m["expenses"],
                    "status": "PASS" if abs(float(m_exp) - exp_m["expenses"]) < 0.01 else "FAIL",
                }
            )
            reconciliation_items.append(
                {
                    "metric": f"monthly_income_{m_str}",
                    "expected": exp_m["income"],
                    "actual": float(m_inc),
                    "difference": float(m_inc) - exp_m["income"],
                    "status": "PASS" if abs(float(m_inc) - exp_m["income"]) < 0.01 else "FAIL",
                }
            )

        # 4. Category Spending Mart Verification
        cat_rows = con.execute(
            """
            SELECT spending_category, total_spent, transaction_count
            FROM main.gold_category_spending
            WHERE user_id = ?
            """,
            [primary_user],
        ).fetchall()

        for cat, spent, count in cat_rows:
            exp_cat = expected_analytics["categories"].get(cat, {"spent": 0.0, "count": 0})
            reconciliation_items.append(
                {
                    "metric": f"category_{cat}_spent",
                    "expected": exp_cat["spent"],
                    "actual": float(spent),
                    "difference": float(spent) - exp_cat["spent"],
                    "status": "PASS" if abs(float(spent) - exp_cat["spent"]) < 0.01 else "FAIL",
                }
            )

        # 5. Quarantine Verification
        quarantine_file = quarantine_dir / "rejected_events.jsonl"
        quarantine_count = 0
        if quarantine_file.exists():
            with open(quarantine_file, encoding="utf-8") as qf:
                quarantine_count = sum(1 for line in qf if line.strip())

        reconciliation_items.append(
            {
                "metric": "quarantined_records",
                "expected": 2,
                "actual": quarantine_count,
                "difference": quarantine_count - 2,
                "status": "PASS" if quarantine_count == 2 else "FAIL",
            }
        )

    overall_pass = all(item["status"] == "PASS" for item in reconciliation_items)

    final_report = {
        "timestamp": datetime.now().isoformat(),
        "primary_user": primary_user,
        "overall_status": "PASS" if overall_pass else "FAIL",
        "pipeline_execution": {
            "silver_stats": silver_stats,
            "silver_idempotency_second_run": second_run_stats,
            "duckdb_rows_synced": synced_rows,
            "dbt_models_passed": len(run_res.result),
            "dbt_tests_passed": len(test_res.result),
            "quarantined_records": quarantine_count,
            "ml_anomalies_detected": ml_res["anomalies_detected"],
            "ml_high_severity_count": ml_res["high_severity_count"],
        },
        "independent_expected_totals": expected_analytics,
        "reconciliation": reconciliation_items,
    }

    # Save to data/synthetic/reports/analytics_reconciliation.json
    out_file = base_dir / "reports" / "analytics_reconciliation.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2)

    logger.info(
        "Saved analytics reconciliation report to %s. Status: %s",
        out_file,
        final_report["overall_status"],
    )
    return final_report


if __name__ == "__main__":
    run_synthetic_pipeline_and_validate()
