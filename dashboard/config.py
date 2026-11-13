import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DashboardConfig:
    """Dashboard configuration settings and database path resolution."""

    duckdb_path: Path = Path(os.getenv("FINPULSE_DUCKDB_PATH", "data/warehouse/finpulse.duckdb"))
    app_title: str = "FinPulse — Financial Intelligence Dashboard"
    app_icon: str = "⚡"
    default_currency: str = "INR"
    page_size: int = 25


config = DashboardConfig()
