import os
from pathlib import Path


class OrchestrationConfig:
    """Configuration paths and settings for FinPulse pipeline orchestration."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        bronze_path: str | Path | None = None,
        silver_path: str | Path | None = None,
        duckdb_path: str | Path | None = None,
        dbt_project_dir: str | Path | None = None,
        dbt_profiles_dir: str | Path | None = None,
        raw_samples_dir: str | Path | None = None,
    ):
        self.base_dir = Path(base_dir or os.getenv("FINPULSE_BASE_DIR", "."))
        self.bronze_path = Path(
            bronze_path or os.getenv("FINPULSE_BRONZE_PATH", self.base_dir / "data/lake/bronze")
        )
        self.silver_path = Path(
            silver_path
            or os.getenv("FINPULSE_SILVER_PATH", self.base_dir / "data/lake/silver/transactions")
        )
        self.duckdb_path = Path(
            duckdb_path
            or os.getenv("FINPULSE_DUCKDB_PATH", self.base_dir / "data/warehouse/finpulse.duckdb")
        )
        self.dbt_project_dir = str(dbt_project_dir or os.getenv("FINPULSE_DBT_PROJECT_DIR", "dbt"))
        self.dbt_profiles_dir = str(
            dbt_profiles_dir or os.getenv("FINPULSE_DBT_PROFILES_DIR", "dbt")
        )
        self.raw_samples_dir = Path(
            raw_samples_dir
            or os.getenv("FINPULSE_RAW_SAMPLES_DIR", self.base_dir / "data/raw_samples")
        )
        self.lock_path = self.duckdb_path.parent / ".lock"


default_config = OrchestrationConfig()
