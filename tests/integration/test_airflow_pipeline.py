import os
from datetime import UTC, datetime
from decimal import Decimal

import duckdb
import pyarrow as pa
import pytest
from deltalake import write_deltalake

from finpulse.orchestration.config import OrchestrationConfig
from finpulse.orchestration.tasks import (
    dbt_run_task,
    dbt_test_task,
    ingest_bronze_task,
    warehouse_sync_task,
)


@pytest.fixture
def integration_env(tmp_path):
    """Sets up a complete isolated directory structure for integration testing."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    bronze_dir = tmp_path / "bronze"
    bronze_dir.mkdir()
    silver_dir = tmp_path / "silver"
    warehouse_dir = tmp_path / "warehouse"
    warehouse_dir.mkdir()
    duckdb_file = warehouse_dir / "finpulse.duckdb"

    # Create a valid raw UPI CSV file
    sample_csv = raw_dir / "sample_upi.csv"
    sample_csv.write_text(
        "date,amount,type,merchant\n"
        "10-11-2026,500.00,DR,Swiggy\n"
        "10-11-2026,1500.00,DR,Amazon\n",
        encoding="utf-8",
    )

    config = OrchestrationConfig(
        base_dir=tmp_path,
        bronze_path=bronze_dir,
        silver_path=silver_dir,
        duckdb_path=duckdb_file,
        raw_samples_dir=raw_dir,
    )

    return config


def test_end_to_end_orchestrated_pipeline_flow(integration_env):
    """
    Verifies that all 5 tasks execute sequentially and data flows across all layers:
    Raw -> Bronze -> Silver -> Warehouse -> dbt -> Tests.
    """
    cfg = integration_env

    # 1. Task 1: Bronze Ingestion
    ingest_res = ingest_bronze_task(config=cfg, user_id="airflow_user")
    assert ingest_res["events_ingested"] == 2
    assert ingest_res["files_processed"] == 1
    assert ingest_res["status"] == "SUCCESS"

    # 2. Task 2: Silver Transformation
    # We populate a Silver Delta table with canonical records to test warehouse sync and dbt
    data = [
        {
            "transaction_id": "txn_001",
            "user_id": "airflow_user",
            "amount": Decimal("500.00"),
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 11, 10, 10, 0, tzinfo=UTC),
            "merchant_raw": "SWIGGY",
            "merchant_normalized": "Swiggy",
            "reference_id": "REF1",
            "source_type": "UPI_CSV",
            "deduplication_key": "key_001",
            "processed_at": datetime(2026, 11, 10, 10, 5, tzinfo=UTC),
            "schema_version": "1.0",
        },
        {
            "transaction_id": "txn_002",
            "user_id": "airflow_user",
            "amount": Decimal("1500.00"),
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 11, 10, 12, 0, tzinfo=UTC),
            "merchant_raw": "AMAZON",
            "merchant_normalized": "Amazon",
            "reference_id": "REF2",
            "source_type": "UPI_CSV",
            "deduplication_key": "key_002",
            "processed_at": datetime(2026, 11, 10, 12, 5, tzinfo=UTC),
            "schema_version": "1.0",
        },
    ]
    schema = pa.schema([
        ("transaction_id", pa.string()),
        ("user_id", pa.string()),
        ("amount", pa.decimal128(18, 2)),
        ("currency", pa.string()),
        ("direction", pa.string()),
        ("transaction_timestamp", pa.timestamp("us", tz="UTC")),
        ("merchant_raw", pa.string()),
        ("merchant_normalized", pa.string()),
        ("reference_id", pa.string()),
        ("source_type", pa.string()),
        ("deduplication_key", pa.string()),
        ("processed_at", pa.timestamp("us", tz="UTC")),
        ("schema_version", pa.string()),
    ])
    table = pa.Table.from_pylist(data, schema=schema)
    write_deltalake(str(cfg.silver_path), table, mode="overwrite")

    # 3. Task 3: Warehouse Synchronization
    sync_res = warehouse_sync_task(config=cfg)
    assert sync_res["success"] is True
    assert sync_res["rows_synced"] == 2

    # Set duckdb path environment variable for dbt
    os.environ["FINPULSE_DUCKDB_PATH"] = str(cfg.duckdb_path)
    try:
        # 4. Task 4: dbt Transformations
        dbt_run_res = dbt_run_task(project_dir="dbt", profiles_dir="dbt", config=cfg)
        assert dbt_run_res["success"] is True
        assert dbt_run_res["models_run"] == 7

        # 5. Task 5: Data Quality Validation
        dbt_test_res = dbt_test_task(project_dir="dbt", profiles_dir="dbt", config=cfg)
        assert dbt_test_res["success"] is True
        assert dbt_test_res["tests_run"] == 27

        # Assert data landed correctly in Gold Marts
        with duckdb.connect(str(cfg.duckdb_path)) as con:
            daily = con.execute(
                "SELECT total_debit_amount FROM main.gold_daily_spending"
            ).fetchall()
            assert daily[0][0] == Decimal("2000.00")
    finally:
        os.environ.pop("FINPULSE_DUCKDB_PATH", None)


def test_upstream_failure_blocks_downstream(integration_env):
    """
    Verifies that a failure in an upstream step raises an exception,
    preventing downstream tasks from continuing.
    """
    cfg = integration_env

    # Simulate bad raw file causing ingestion failure
    bad_csv = cfg.raw_samples_dir / "corrupted.csv"
    bad_csv.write_text("bad,header\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Bronze ingestion failed"):
        ingest_bronze_task(config=cfg)


def test_empty_raw_folder_handling(integration_env):
    """Verifies that an empty raw input directory does not fail or halt pipeline."""
    cfg = integration_env

    # Remove all raw sample files
    for f in cfg.raw_samples_dir.iterdir():
        f.unlink()

    res = ingest_bronze_task(config=cfg)
    assert res["events_ingested"] == 0
    assert res["files_processed"] == 0
    assert res["status"] == "NO_NEW_FILES"
