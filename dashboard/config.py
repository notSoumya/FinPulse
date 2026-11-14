
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class DashboardConfig:
    """Dashboard configuration settings and database path resolution."""

    duckdb_path: Path = Path(
        os.getenv(
            "FINPULSE_DUCKDB_PATH",
            str(
                PROJECT_ROOT
                / "data"
                / "synthetic"
                / "warehouse"
                / "finpulse_synthetic.duckdb"
            ),
        )
    ).resolve()

    app_title: str = "FinPulse - Financial Intelligence Dashboard"
    app_icon: str = "⚡"
    default_currency: str = "INR"
    page_size: int = 25

config = DashboardConfig()