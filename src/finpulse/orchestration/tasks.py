import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dbt.cli.main import dbtRunner

from finpulse.bronze.storage import BronzeStorage
from finpulse.ingestion.parsers.card_pdf_parser import parse_card_pdf
from finpulse.ingestion.parsers.upi_parser import parse_upi_csv
from finpulse.orchestration.config import OrchestrationConfig, default_config
from finpulse.processing.silver_pipeline import SilverPipeline
from finpulse.warehouse.loader import WarehouseLoader

logger = logging.getLogger(__name__)


@contextmanager
def file_lock(lock_file_path: Path):
    """Simple file lock to prevent concurrent writers on local DuckDB / Delta table."""
    lock_file_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_file_path.exists():
        logger.warning("Lock file %s exists; waiting or checking stale lock.", lock_file_path)
    try:
        lock_file_path.touch(exist_ok=False)
        yield
    finally:
        if lock_file_path.exists():
            try:
                lock_file_path.unlink()
            except OSError:
                pass


def ingest_bronze_task(
    raw_dir: str | Path | None = None,
    bronze_path: str | Path | None = None,
    user_id: str = "batch_user",
    config: OrchestrationConfig | None = None,
) -> dict[str, Any]:
    """
    Task 1: Bounded batch ingestion.
    Discovers pending input files in raw_dir and converts them to Bronze JSONL events.
    """
    cfg = config or default_config
    input_dir = Path(raw_dir or cfg.raw_samples_dir)
    target_bronze = Path(bronze_path or cfg.bronze_path)

    logger.info("Executing Bronze Ingestion Task. Checking: %s", input_dir)
    bronze_storage = BronzeStorage(target_bronze)

    if not input_dir.exists():
        logger.info("Raw input directory %s does not exist; zero events ingested.", input_dir)
        return {"events_ingested": 0, "files_processed": 0, "status": "NO_NEW_FILES"}

    raw_files = [f for f in input_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
    if not raw_files:
        logger.info("No input files found in %s; zero events ingested.", input_dir)
        return {"events_ingested": 0, "files_processed": 0, "status": "NO_NEW_FILES"}

    events_ingested = 0
    files_processed = 0

    for file_path in raw_files:
        logger.info("Processing raw file: %s", file_path.name)
        transactions = []
        try:
            if file_path.suffix.lower() == ".csv":
                transactions = parse_upi_csv(str(file_path), user_id=user_id)
            elif file_path.suffix.lower() == ".pdf":
                transactions = parse_card_pdf(str(file_path), user_id=user_id)
            else:
                logger.warning("Unsupported raw file format %s; skipping.", file_path.name)
                continue

            for tx in transactions:
                event = {
                    "event_id": f"evt_{tx.transaction_id}",
                    "event_timestamp": datetime.now(UTC).isoformat(),
                    "schema_version": "1.0",
                    "event_type": "TRANSACTION_CREATED",
                    "payload": tx.model_dump(mode="json"),
                }
                if bronze_storage.write_event(event):
                    events_ingested += 1

            files_processed += 1
        except Exception as exc:
            logger.error("Failed to parse file %s: %s", file_path.name, exc)
            raise RuntimeError(f"Bronze ingestion failed on {file_path.name}: {exc}") from exc

    logger.info(
        "Bronze Ingestion completed: %d events from %d files.",
        events_ingested,
        files_processed,
    )
    return {
        "events_ingested": events_ingested,
        "files_processed": files_processed,
        "status": "SUCCESS",
    }


def silver_pipeline_task(
    silver_path: str | Path | None = None,
    bronze_path: str | Path | None = None,
    config: OrchestrationConfig | None = None,
) -> dict[str, Any]:
    """
    Task 2: Silver transformation.
    Cleans, normalizes, deduplicates, and writes clean transactions to Delta Lake.
    """
    logger.info("Executing Silver Transformation Task...")
    pipeline = SilverPipeline()
    stats = pipeline.run()
    logger.info("Silver pipeline completed. Stats: %s", stats)
    return {
        "success": True,
        "events_read": stats.get("events_read", 0),
        "transactions_written": stats.get("transactions_written", 0),
        "duplicates_skipped": stats.get("duplicates_skipped", 0),
        "transactions_quarantined": stats.get("transactions_quarantined", 0),
        "events_skipped_by_checkpoint": stats.get("events_skipped_by_checkpoint", 0),
    }


def warehouse_sync_task(
    silver_path: str | Path | None = None,
    db_path: str | Path | None = None,
    config: OrchestrationConfig | None = None,
) -> dict[str, Any]:
    """
    Task 3: Warehouse synchronization.
    Syncs transactions from Delta Lake into DuckDB table silver.transactions.
    """
    cfg = config or default_config
    target_silver = silver_path or cfg.silver_path
    target_db = db_path or cfg.duckdb_path

    logger.info("Executing Warehouse Sync Task from %s to %s...", target_silver, target_db)
    with file_lock(cfg.lock_path):
        loader = WarehouseLoader(silver_path=target_silver, db_path=target_db)
        rows_synced = loader.sync()

    logger.info("Warehouse sync completed. Rows synced: %d", rows_synced)
    return {
        "success": True,
        "rows_synced": rows_synced,
    }


def dbt_run_task(
    project_dir: str | Path | None = None,
    profiles_dir: str | Path | None = None,
    config: OrchestrationConfig | None = None,
) -> dict[str, Any]:
    """
    Task 4: dbt transformations.
    Builds staging views, intermediate views, and Gold analytical marts in DuckDB.
    """
    cfg = config or default_config
    p_dir = str(project_dir or cfg.dbt_project_dir)
    prof_dir = str(profiles_dir or cfg.dbt_profiles_dir)

    logger.info(
        "Executing dbt Transformations Task (project: %s, profiles: %s)...",
        p_dir,
        prof_dir,
    )
    runner = dbtRunner()
    with file_lock(cfg.lock_path):
        res = runner.invoke(["run", "--project-dir", p_dir, "--profiles-dir", prof_dir])

    if not res.success:
        logger.error("dbt run failed: %s", res.exception)
        raise RuntimeError(f"dbt run failed: {res.exception}")

    models_count = len(res.result) if res.result else 0
    logger.info("dbt run completed successfully. Models created: %d", models_count)
    return {
        "success": True,
        "models_run": models_count,
    }


def dbt_test_task(
    project_dir: str | Path | None = None,
    profiles_dir: str | Path | None = None,
    config: OrchestrationConfig | None = None,
) -> dict[str, Any]:
    """
    Task 5: Data quality validation.
    Executes all configured dbt generic and business data tests.
    """
    cfg = config or default_config
    p_dir = str(project_dir or cfg.dbt_project_dir)
    prof_dir = str(profiles_dir or cfg.dbt_profiles_dir)

    logger.info(
        "Executing Data Quality Validation Task (project: %s, profiles: %s)...",
        p_dir,
        prof_dir,
    )
    runner = dbtRunner()
    res = runner.invoke(["test", "--project-dir", p_dir, "--profiles-dir", prof_dir])

    if not res.success:
        logger.error("dbt test failed: %s", res.exception)
        raise RuntimeError(f"dbt test data quality checks failed: {res.exception}")

    tests_count = len(res.result) if res.result else 0
    logger.info("Data quality validation completed successfully. Tests passed: %d", tests_count)
    return {
        "success": True,
        "tests_run": tests_count,
    }
