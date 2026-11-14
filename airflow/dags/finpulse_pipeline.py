"""
FinPulse End-to-End Orchestrated Pipeline DAG.
Orchestrates: Bronze -> Silver -> DuckDB -> dbt -> Quality Tests.
"""

import logging
import os
from datetime import UTC, datetime, timedelta

from finpulse.orchestration.tasks import (
    dbt_run_task,
    dbt_test_task,
    ingest_bronze_task,
    silver_pipeline_task,
    warehouse_sync_task,
)

logger = logging.getLogger(__name__)

default_args = {
    "owner": "finpulse",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(minutes=15),
    "email_on_failure": False,
}


def create_finpulse_dag():
    """Factory function to build and configure the FinPulse orchestration DAG."""
    try:
        from airflow.operators.python import PythonOperator
        from airflow.utils.trigger_rule import TriggerRule

        from airflow import DAG
    except ImportError:
        logger.warning(
            "Apache Airflow is not installed in the current environment. "
            "DAG definition returned as None or for container runtime."
        )
        return None

    schedule_interval = os.getenv("FINPULSE_DAG_SCHEDULE", "@daily")

    dag = DAG(
        dag_id="finpulse_end_to_end_pipeline",
        default_args=default_args,
        description="Automated end-to-end pipeline: Bronze -> Silver -> DuckDB -> dbt",
        schedule_interval=schedule_interval,
        start_date=datetime(2026, 1, 1, tzinfo=UTC),
        catchup=False,
        max_active_runs=1,
        tags=["finpulse", "financial", "delta-lake", "duckdb", "dbt"],
    )

    with dag:
        bronze_ingestion = PythonOperator(
            task_id="bronze_ingestion",
            python_callable=ingest_bronze_task,
            trigger_rule=TriggerRule.ALL_SUCCESS,
        )

        silver_transformation = PythonOperator(
            task_id="silver_transformation",
            python_callable=silver_pipeline_task,
            trigger_rule=TriggerRule.ALL_SUCCESS,
        )

        warehouse_sync = PythonOperator(
            task_id="warehouse_sync",
            python_callable=warehouse_sync_task,
            trigger_rule=TriggerRule.ALL_SUCCESS,
        )

        dbt_transformations = PythonOperator(
            task_id="dbt_transformations",
            python_callable=dbt_run_task,
            trigger_rule=TriggerRule.ALL_SUCCESS,
        )

        data_quality_validation = PythonOperator(
            task_id="data_quality_validation",
            python_callable=dbt_test_task,
            trigger_rule=TriggerRule.ALL_SUCCESS,
        )

        # Enforce linear pipeline dependency
        (
            bronze_ingestion
            >> silver_transformation
            >> warehouse_sync
            >> dbt_transformations
            >> data_quality_validation
        )

    return dag


# Top-level DAG object for Airflow discovery
dag = create_finpulse_dag()
