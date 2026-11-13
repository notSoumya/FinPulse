import logging

from dbt.cli.main import dbtRunner

from finpulse.warehouse.loader import sync_silver_to_duckdb

logger = logging.getLogger(__name__)


def run_warehouse_pipeline(
    silver_path: str = "data/lake/silver/transactions",
    db_path: str = "data/warehouse/finpulse.duckdb",
    project_dir: str = "dbt",
    profiles_dir: str = "dbt",
) -> dict:
    """
    Sync Silver Delta Lake to DuckDB and run dbt transformations and tests.
    """
    logger.info("Step 1: Syncing Silver Delta Lake to DuckDB...")
    rows_synced = sync_silver_to_duckdb(silver_path=silver_path, db_path=db_path)
    logger.info("Silver sync complete: %d rows synced.", rows_synced)

    runner = dbtRunner()

    logger.info("Step 2: Running dbt models...")
    run_res = runner.invoke(["run", "--project-dir", project_dir, "--profiles-dir", profiles_dir])
    if not run_res.success:
        logger.error("dbt run failed: %s", run_res.exception)
        return {
            "success": False,
            "rows_synced": rows_synced,
            "error": "dbt run failed",
        }

    logger.info("Step 3: Running dbt tests...")
    test_res = runner.invoke(["test", "--project-dir", project_dir, "--profiles-dir", profiles_dir])
    if not test_res.success:
        logger.error("dbt test failed: %s", test_res.exception)
        return {
            "success": False,
            "rows_synced": rows_synced,
            "error": "dbt test failed",
        }

    logger.info("Warehouse pipeline execution successful!")
    return {
        "success": True,
        "rows_synced": rows_synced,
        "dbt_models_run": len(run_res.result) if run_res.result else 0,
        "dbt_tests_run": len(test_res.result) if test_res.result else 0,
    }


__all__ = ["run_warehouse_pipeline"]

