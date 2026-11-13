from unittest.mock import MagicMock, patch

import pytest

from finpulse.orchestration.config import OrchestrationConfig
from finpulse.orchestration.tasks import (
    dbt_run_task,
    dbt_test_task,
    file_lock,
    ingest_bronze_task,
    silver_pipeline_task,
    warehouse_sync_task,
)


def test_file_lock(tmp_path):
    lock_file = tmp_path / "test.lock"
    assert not lock_file.exists()
    with file_lock(lock_file):
        assert lock_file.exists()
    assert not lock_file.exists()


def test_ingest_bronze_task_missing_dir(tmp_path):
    missing_dir = tmp_path / "non_existent_raw"
    bronze_dir = tmp_path / "bronze"
    config = OrchestrationConfig(raw_samples_dir=missing_dir, bronze_path=bronze_dir)

    res = ingest_bronze_task(config=config)
    assert res["events_ingested"] == 0
    assert res["files_processed"] == 0
    assert res["status"] == "NO_NEW_FILES"


def test_ingest_bronze_task_empty_dir(tmp_path):
    empty_dir = tmp_path / "empty_raw"
    empty_dir.mkdir()
    bronze_dir = tmp_path / "bronze"
    config = OrchestrationConfig(raw_samples_dir=empty_dir, bronze_path=bronze_dir)

    res = ingest_bronze_task(config=config)
    assert res["events_ingested"] == 0
    assert res["files_processed"] == 0
    assert res["status"] == "NO_NEW_FILES"


def test_ingest_bronze_task_with_csv(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    sample_csv = raw_dir / "sample_upi.csv"
    sample_csv.write_text(
        "date,amount,type,merchant\n"
        "10-11-2026,500.00,DR,Swiggy\n"
        "11-11-2026,1200.50,CR,Salary\n",
        encoding="utf-8",
    )

    bronze_dir = tmp_path / "bronze"
    config = OrchestrationConfig(raw_samples_dir=raw_dir, bronze_path=bronze_dir)

    res = ingest_bronze_task(config=config, user_id="test_user")
    assert res["events_ingested"] == 2
    assert res["files_processed"] == 1
    assert res["status"] == "SUCCESS"

    # Verify Bronze files exist
    bronze_files = list(bronze_dir.rglob("*.jsonl"))
    assert len(bronze_files) > 0


def test_ingest_bronze_task_invalid_csv_raises(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    bad_csv = raw_dir / "bad.csv"
    bad_csv.write_text("invalid,columns\n1,2\n", encoding="utf-8")

    bronze_dir = tmp_path / "bronze"
    config = OrchestrationConfig(raw_samples_dir=raw_dir, bronze_path=bronze_dir)

    with pytest.raises(RuntimeError, match="Bronze ingestion failed on bad.csv"):
        ingest_bronze_task(config=config)


@patch("finpulse.orchestration.tasks.SilverPipeline")
def test_silver_pipeline_task(mock_pipeline_cls):
    mock_instance = MagicMock()
    mock_instance.run.return_value = {
        "events_read": 10,
        "transactions_written": 8,
        "duplicates_skipped": 2,
        "transactions_quarantined": 0,
        "events_skipped_by_checkpoint": 0,
    }
    mock_pipeline_cls.return_value = mock_instance

    res = silver_pipeline_task()
    assert res["success"] is True
    assert res["events_read"] == 10
    assert res["transactions_written"] == 8
    assert res["duplicates_skipped"] == 2


@patch("finpulse.orchestration.tasks.WarehouseLoader")
def test_warehouse_sync_task(mock_loader_cls, tmp_path):
    mock_instance = MagicMock()
    mock_instance.sync.return_value = 15
    mock_loader_cls.return_value = mock_instance

    config = OrchestrationConfig(
        silver_path=tmp_path / "silver",
        duckdb_path=tmp_path / "warehouse" / "test.duckdb",
    )
    res = warehouse_sync_task(config=config)
    assert res["success"] is True
    assert res["rows_synced"] == 15


@patch("finpulse.orchestration.tasks.dbtRunner")
def test_dbt_run_task_success(mock_runner_cls, tmp_path):
    mock_runner = MagicMock()
    mock_runner.invoke.return_value = MagicMock(success=True, result=[1, 2, 3, 4, 5, 6, 7])
    mock_runner_cls.return_value = mock_runner

    config = OrchestrationConfig(duckdb_path=tmp_path / "test.duckdb")
    res = dbt_run_task(config=config)
    assert res["success"] is True
    assert res["models_run"] == 7


@patch("finpulse.orchestration.tasks.dbtRunner")
def test_dbt_run_task_failure(mock_runner_cls, tmp_path):
    mock_runner = MagicMock()
    mock_runner.invoke.return_value = MagicMock(success=False, exception="Syntax error in SQL")
    mock_runner_cls.return_value = mock_runner

    config = OrchestrationConfig(duckdb_path=tmp_path / "test.duckdb")
    with pytest.raises(RuntimeError, match="dbt run failed"):
        dbt_run_task(config=config)


@patch("finpulse.orchestration.tasks.dbtRunner")
def test_dbt_test_task_success(mock_runner_cls, tmp_path):
    mock_runner = MagicMock()
    mock_runner.invoke.return_value = MagicMock(success=True, result=list(range(27)))
    mock_runner_cls.return_value = mock_runner

    config = OrchestrationConfig(duckdb_path=tmp_path / "test.duckdb")
    res = dbt_test_task(config=config)
    assert res["success"] is True
    assert res["tests_run"] == 27


@patch("finpulse.orchestration.tasks.dbtRunner")
def test_dbt_test_task_failure(mock_runner_cls, tmp_path):
    mock_runner = MagicMock()
    mock_runner.invoke.return_value = MagicMock(success=False, exception="Assertion failed")
    mock_runner_cls.return_value = mock_runner

    config = OrchestrationConfig(duckdb_path=tmp_path / "test.duckdb")
    with pytest.raises(RuntimeError, match="dbt test data quality checks failed"):
        dbt_test_task(config=config)
