from pathlib import Path
from typing import Any

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

from finpulse.common.models import SilverTransaction


class SilverWriter:
    """Writes transactions idempotently into a Delta Lake Silver table."""

    def __init__(
        self,
        table_path: str | Path = "data/lake/silver/transactions",
    ):
        self.table_path = Path(table_path)

    @staticmethod
    def _to_arrow_table(
        transactions: list[SilverTransaction],
    ) -> pa.Table:
        records = [
            transaction.model_dump(mode="python")
            for transaction in transactions
        ]
        return pa.Table.from_pylist(records)

    def write(
        self,
        transactions: list[SilverTransaction],
    ) -> int:
        """
        Insert only transactions whose deduplication_key
        does not already exist.

        Returns the number of newly inserted rows.
        """

        if not transactions:
            return 0

        # Also prevent duplicate keys within the same incoming batch.
        unique_transactions = {
            transaction.deduplication_key: transaction
            for transaction in transactions
        }

        arrow_table = self._to_arrow_table(
            list(unique_transactions.values())
        )

        self.table_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        delta_log = self.table_path / "_delta_log"

        if not delta_log.exists():
            write_deltalake(
                str(self.table_path),
                arrow_table,
                mode="error",
            )
            return len(unique_transactions)

        delta_table = DeltaTable(str(self.table_path))

        merger = delta_table.merge(
            source=arrow_table,
            predicate=(
                "target.deduplication_key = source.deduplication_key"
            ),
            source_alias="source",
            target_alias="target",
        )

        result = merger.when_not_matched_insert_all().execute()

        return int(result.get("num_target_rows_inserted", 0))

    def read_all(self) -> list[dict[str, Any]]:
        """Read all records from the Silver Delta table."""

        if not (self.table_path / "_delta_log").exists():
            return []

        table = DeltaTable(str(self.table_path))
        return table.to_pyarrow_table().to_pylist()