import importlib.util
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

DAG_FILE_PATH = Path("airflow/dags/finpulse_pipeline.py")


def _load_dag_module():
    spec = importlib.util.spec_from_file_location("finpulse_pipeline", DAG_FILE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["finpulse_pipeline"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_airflow_dag_importable():
    """Verify the DAG file can be parsed and imported cleanly."""
    dag_mod = _load_dag_module()

    assert hasattr(dag_mod, "create_finpulse_dag")
    assert hasattr(dag_mod, "default_args")
    assert dag_mod.default_args["retries"] == 2
    assert dag_mod.default_args["retry_delay"] == timedelta(minutes=1)
    assert dag_mod.default_args["execution_timeout"] == timedelta(minutes=15)


def test_airflow_dag_structure_with_mocked_airflow():
    """Verify DAG structure, task IDs, and dependencies when Airflow is present."""
    mock_dag_cls = MagicMock()
    mock_operator_cls = MagicMock()
    mock_trigger_rule = MagicMock()
    mock_trigger_rule.ALL_SUCCESS = "all_success"

    created_tasks = {}

    class MockTask:
        def __init__(self, task_id, **kwargs):
            self.task_id = task_id
            self.downstream_list = []
            self.upstream_list = []
            created_tasks[task_id] = self

        def __rshift__(self, other):
            self.downstream_list.append(other)
            other.upstream_list.append(self)
            return other

    mock_operator_cls.side_effect = lambda **kwargs: MockTask(**kwargs)

    mock_dag_instance = MagicMock()
    mock_dag_instance.task_dict = created_tasks
    mock_dag_cls.return_value.__enter__.return_value = mock_dag_instance
    mock_dag_cls.return_value = mock_dag_instance

    with patch.dict(
        sys.modules,
        {
            "airflow": MagicMock(DAG=mock_dag_cls),
            "airflow.operators.python": MagicMock(PythonOperator=mock_operator_cls),
            "airflow.utils.trigger_rule": MagicMock(TriggerRule=mock_trigger_rule),
        },
    ):
        dag_mod = _load_dag_module()
        dag = dag_mod.create_finpulse_dag()
        assert dag is not None

        expected_tasks = [
            "bronze_ingestion",
            "silver_transformation",
            "warehouse_sync",
            "dbt_transformations",
            "data_quality_validation",
        ]
        for task_id in expected_tasks:
            assert task_id in created_tasks, f"Task {task_id} missing from DAG"

        assert (
            created_tasks["silver_transformation"]
            in created_tasks["bronze_ingestion"].downstream_list
        )
        assert (
            created_tasks["warehouse_sync"]
            in created_tasks["silver_transformation"].downstream_list
        )
        assert (
            created_tasks["dbt_transformations"]
            in created_tasks["warehouse_sync"].downstream_list
        )
        assert (
            created_tasks["data_quality_validation"]
            in created_tasks["dbt_transformations"].downstream_list
        )
