import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from dashboard.config import config

logger = logging.getLogger(__name__)


class DatabaseUnavailableError(Exception):
    """Raised when the DuckDB warehouse database cannot be found or opened."""
    pass


def is_database_available(db_path: Path | None = None) -> bool:
    """Check if the DuckDB warehouse file exists and is accessible."""
    target_path = Path(db_path or config.duckdb_path)
    return target_path.exists() and target_path.is_file()


@contextmanager
def get_db_connection(
    db_path: Path | None = None,
    read_only: bool = True,
) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """
    Context manager providing safe read-only DuckDB connection.
    Guarantees that warehouse tables cannot be accidentally mutated by the dashboard.
    """
    target_path = Path(db_path or config.duckdb_path)

    if not target_path.exists():
        logger.warning("DuckDB database file not found at: %s", target_path)
        raise DatabaseUnavailableError(
            f"Warehouse database file not found at: {target_path}. "
            "Please run the FinPulse pipeline to populate the warehouse."
        )

    try:
        # read_only=True allows concurrent readers alongside file-locked writers
        con = duckdb.connect(str(target_path), read_only=read_only)
        try:
            yield con
        finally:
            con.close()
    except Exception as exc:
        logger.error("Failed to connect to DuckDB: %s", exc)
        raise DatabaseUnavailableError(f"Failed to connect to DuckDB warehouse: {exc}") from exc
