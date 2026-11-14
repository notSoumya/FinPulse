import logging
from pathlib import Path

import duckdb
from deltalake import DeltaTable

logger = logging.getLogger(__name__)


class WarehouseLoader:
    """
    Syncs transactions from the Delta Lake Silver table into the local DuckDB warehouse.
    """

    def __init__(
        self,
        silver_path: str | Path = "data/lake/silver/transactions",
        db_path: str | Path = "data/warehouse/finpulse.duckdb",
    ):
        self.silver_path = Path(silver_path)
        self.db_path = Path(db_path)

    def sync(self) -> int:
        """
        Read the Delta Lake Silver table and sync records into DuckDB table silver.transactions.
        Returns the number of rows synced.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        delta_log = self.silver_path / "_delta_log"
        if not delta_log.exists():
            logger.warning("Silver Delta table not found at %s", self.silver_path)
            with duckdb.connect(str(self.db_path)) as con:
                con.execute("CREATE SCHEMA IF NOT EXISTS silver")
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS silver.transactions (
                        transaction_id VARCHAR,
                        user_id VARCHAR,
                        amount DECIMAL(18, 2),
                        currency VARCHAR,
                        direction VARCHAR,
                        transaction_timestamp TIMESTAMPTZ,
                        merchant_raw VARCHAR,
                        merchant_normalized VARCHAR,
                        reference_id VARCHAR,
                        source_type VARCHAR,
                        deduplication_key VARCHAR,
                        processed_at TIMESTAMPTZ,
                        schema_version VARCHAR
                    )
                    """
                )
            return 0

        logger.info("Reading Silver Delta table from %s", self.silver_path)
        delta_table = DeltaTable(str(self.silver_path))
        arrow_table = delta_table.to_pyarrow_table()
        row_count = arrow_table.num_rows

        with duckdb.connect(str(self.db_path)) as con:
            con.execute("CREATE SCHEMA IF NOT EXISTS silver")
            con.register("_arrow_silver_tx", arrow_table)
            con.execute(
                "CREATE OR REPLACE TABLE silver.transactions AS SELECT * FROM _arrow_silver_tx"
            )
            con.unregister("_arrow_silver_tx")

        logger.info("Successfully synced %d rows into DuckDB silver.transactions", row_count)
        return row_count


def sync_silver_to_duckdb(
    silver_path: str | Path = "data/lake/silver/transactions",
    db_path: str | Path = "data/warehouse/finpulse.duckdb",
) -> int:
    """Convenience function to sync Silver Delta Lake to DuckDB."""
    loader = WarehouseLoader(silver_path=silver_path, db_path=db_path)
    return loader.sync()
