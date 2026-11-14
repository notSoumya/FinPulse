"""
Integration Test Suite: Synthetic Data & End-to-End Pipeline Validation.

Exercises:
- Full synthetic data generation and manifest verification
- Independent parser validation (UPI CSV, Card PDF, Bank SMS, Manual)
- Silver pipeline transformation and idempotency (second run writes 0 rows)
- Quarantine isolation of malformed and invalid records
- DuckDB warehouse synchronization and dbt model execution
- Complete mathematical reconciliation of financial metrics
- Dashboard queries against synthetic warehouse
- Edge cases: corrupt PDF, empty files, missing mandatory fields
"""

import json
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from dashboard.queries import get_filter_bounds, get_overview_kpis
from finpulse.ingestion.parsers.card_pdf_parser import parse_card_pdf
from finpulse.ingestion.parsers.manual_parser import parse_manual
from finpulse.ingestion.parsers.sms_parser import parse_bank_sms
from finpulse.ingestion.parsers.upi_parser import parse_upi_csv
from tests.fixtures.synthetic_data.generate_synthetic_data import (
    SyntheticConfig,
    generate_all_synthetic_files,
)
from tests.fixtures.synthetic_data.validate_parsers import validate_all_parsers
from tests.validation.validate_synthetic_analytics import (
    run_synthetic_pipeline_and_validate,
)


@pytest.fixture(scope="module")
def synthetic_env():
    """Ensure synthetic data is generated and validated for tests."""
    manifest = generate_all_synthetic_files(SyntheticConfig())
    parser_report = validate_all_parsers()
    pipeline_report = run_synthetic_pipeline_and_validate()
    return {
        "manifest": manifest,
        "parser_report": parser_report,
        "pipeline_report": pipeline_report,
    }


def test_synthetic_data_generation_manifest(synthetic_env):
    manifest = synthetic_env["manifest"]
    assert manifest["counts"]["total_valid"] == 120
    assert manifest["counts"]["upi_valid"] == 40
    assert manifest["counts"]["card_valid"] == 35
    assert manifest["counts"]["sms_valid"] == 25
    assert manifest["counts"]["manual_valid"] == 20
    for key, path_str in manifest["files"].items():
        assert Path(path_str).exists(), f"File {key} not found at {path_str}"


def test_parser_validation_report(synthetic_env):
    report = synthetic_env["parser_report"]
    assert report["overall_status"] == "PASS"
    for parser_name, details in report["parsers"].items():
        assert details["status"] == "PASS", f"Parser {parser_name} failed validation"
        assert details["valid_count_parsed"] == details["valid_count_expected"]


def test_silver_pipeline_execution_and_idempotency(synthetic_env):
    report = synthetic_env["pipeline_report"]
    exec_stats = report["pipeline_execution"]
    assert exec_stats["silver_stats"]["transactions_written"] == 120
    assert exec_stats["silver_stats"]["transactions_quarantined"] == 2
    # Verify strict idempotency on second run
    assert exec_stats["silver_idempotency_second_run"]["transactions_written"] == 0
    assert exec_stats["duckdb_rows_synced"] == 120


def test_quarantine_isolation(synthetic_env):
    quarantine_file = Path("data/synthetic/quarantine/rejected_transactions/rejected_events.jsonl")
    assert quarantine_file.exists()
    with open(quarantine_file, encoding="utf-8") as f:
        quarantined = [json.loads(line) for line in f if line.strip()]
    assert len(quarantined) == 2
    # Quarantined records must not exist in DuckDB silver.transactions
    warehouse_db = Path("data/synthetic/warehouse/finpulse_synthetic.duckdb")
    with duckdb.connect(str(warehouse_db)) as con:
        bad_ids = con.execute(
            "SELECT count(*) FROM silver.transactions WHERE transaction_id = 'tx_bad_amount'"
        ).fetchone()[0]
        assert bad_ids == 0


def test_synthetic_analytics_reconciliation(synthetic_env):
    report = synthetic_env["pipeline_report"]
    assert report["overall_status"] == "PASS"
    for item in report["reconciliation"]:
        assert item["status"] == "PASS", f"Reconciliation failed on {item['metric']}: {item}"


def test_dashboard_queries_against_synthetic_warehouse(synthetic_env):
    warehouse_db = Path("data/synthetic/warehouse/finpulse_synthetic.duckdb")
    bounds = get_filter_bounds(db_path=warehouse_db)
    assert bounds["min_date"] is not None
    assert "synthetic_user_1" in bounds["users"]
    assert "INR" in bounds["currencies"]

    kpis = get_overview_kpis(user_id="synthetic_user_1", currency="INR", db_path=warehouse_db)
    assert kpis["total_transactions"] == 106
    assert kpis["total_income"] == Decimal("227900.00")
    assert kpis["total_expenses"] == Decimal("120563.00")
    assert kpis["net_cash_flow"] == Decimal("107337.00")
    assert kpis["savings_rate_pct"] == pytest.approx(47.1, 0.01)


def test_anomaly_detection_pipeline_execution(synthetic_env):
    report = synthetic_env["pipeline_report"]
    exec_stats = report["pipeline_execution"]
    assert exec_stats["ml_anomalies_detected"] > 0
    assert exec_stats["ml_high_severity_count"] >= 1

    warehouse_db = Path("data/synthetic/warehouse/finpulse_synthetic.duckdb")
    with duckdb.connect(str(warehouse_db)) as con:
        anom_count = con.execute("SELECT count(*) FROM silver.anomalies").fetchone()[0]
        assert anom_count == 120
        high_count = con.execute(
            "SELECT count(*) FROM silver.anomalies WHERE severity = 'High'"
        ).fetchone()[0]
        assert high_count >= 1


def test_anomaly_dashboard_queries(synthetic_env):
    warehouse_db = Path("data/synthetic/warehouse/finpulse_synthetic.duckdb")
    from dashboard.queries import (
        get_anomaly_distributions,
        get_anomaly_investigation_records,
        get_anomaly_kpis,
        get_anomaly_normal_comparison,
        get_anomaly_timeline,
        get_financial_insights,
    )

    kpis = get_anomaly_kpis(user_id="synthetic_user_1", currency="INR", db_path=warehouse_db)
    assert kpis["total_evaluated"] == 106
    assert kpis["total_anomalies"] > 0
    assert kpis["high_severity_count"] >= 1

    timeline = get_anomaly_timeline(
        user_id="synthetic_user_1", currency="INR", db_path=warehouse_db
    )
    assert not timeline.empty

    dist = get_anomaly_distributions(
        "category", user_id="synthetic_user_1", currency="INR", db_path=warehouse_db
    )
    assert not dist.empty

    records, total = get_anomaly_investigation_records(
        user_id="synthetic_user_1", currency="INR", db_path=warehouse_db
    )
    assert total > 0
    assert len(records) > 0
    assert "primary_reason" in records.columns

    comparison = get_anomaly_normal_comparison(
        user_id="synthetic_user_1", currency="INR", db_path=warehouse_db
    )
    assert comparison["normal_count"] > 0
    assert comparison["anomalous_count"] > 0

    insights = get_financial_insights(
        user_id="synthetic_user_1", currency="INR", db_path=warehouse_db
    )
    assert len(insights) >= 3


def test_edge_cases_and_malformed_inputs(tmp_path):
    # 1. Missing mandatory field in manual transaction
    with pytest.raises(Exception):
        parse_manual({"user_id": "u1", "amount": "100.00"})  # missing direction & timestamp

    # 2. Malformed UPI CSV (missing column)
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("date,amount\n2026-09-01,500.00\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required columns"):
        parse_upi_csv(str(bad_csv), "u1")

    # 3. Unreadable / empty PDF
    empty_pdf = tmp_path / "empty.pdf"
    import fitz

    doc = fitz.open()
    doc.new_page()  # empty page with no selectable text
    doc.save(str(empty_pdf))
    doc.close()
    with pytest.raises(ValueError, match="No selectable text found"):
        parse_card_pdf(str(empty_pdf), "u1")

    # 4. Bank SMS without amount
    with pytest.raises(ValueError, match="Transaction amount not found"):
        from datetime import UTC, datetime

        parse_bank_sms("Your account has been debited towards Store.", "u1", datetime.now(UTC))
