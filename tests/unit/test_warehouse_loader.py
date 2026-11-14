from datetime import UTC, datetime
from decimal import Decimal

import duckdb
import pyarrow as pa
import pytest
from deltalake import write_deltalake

from finpulse.warehouse.loader import WarehouseLoader, sync_silver_to_duckdb


@pytest.fixture
def sample_silver_arrow_table():
    data = [
        {
            "transaction_id": "txn_001",
            "user_id": "user_101",
            "amount": Decimal("1499.50"),
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 11, 10, 14, 30, tzinfo=UTC),
            "merchant_raw": "AMZN PAYMENTS INDIA",
            "merchant_normalized": "Amazon",
            "reference_id": "REF12345",
            "source_type": "UPI_CSV",
            "deduplication_key": "dedup_001",
            "processed_at": datetime(2026, 11, 10, 14, 35, tzinfo=UTC),
            "schema_version": "1.0",
        },
        {
            "transaction_id": "txn_002",
            "user_id": "user_101",
            "amount": Decimal("25000.00"),
            "currency": "INR",
            "direction": "CREDIT",
            "transaction_timestamp": datetime(2026, 11, 10, 9, 0, tzinfo=UTC),
            "merchant_raw": "SALARY CREDITED",
            "merchant_normalized": "Salary Credited",
            "reference_id": "REF99999",
            "source_type": "BANK_SMS",
            "deduplication_key": "dedup_002",
            "processed_at": datetime(2026, 11, 10, 9, 5, tzinfo=UTC),
            "schema_version": "1.0",
        },
    ]
    return pa.Table.from_pylist(data)


def test_sync_empty_when_delta_table_missing(tmp_path):
    silver_path = tmp_path / "silver_missing"
    db_path = tmp_path / "warehouse" / "finpulse.duckdb"

    loader = WarehouseLoader(silver_path=silver_path, db_path=db_path)
    count = loader.sync()

    assert count == 0
    assert db_path.exists()

    with duckdb.connect(str(db_path)) as con:
        rows = con.execute("SELECT count(*) FROM silver.transactions").fetchone()[0]
        assert rows == 0


def test_sync_populated_silver_table(tmp_path, sample_silver_arrow_table):
    silver_path = tmp_path / "silver"
    db_path = tmp_path / "warehouse" / "finpulse.duckdb"

    write_deltalake(str(silver_path), sample_silver_arrow_table, mode="error")

    count = sync_silver_to_duckdb(silver_path=silver_path, db_path=db_path)
    assert count == 2

    with duckdb.connect(str(db_path)) as con:
        rows = con.execute(
            "SELECT transaction_id, user_id, amount, direction "
            "FROM silver.transactions ORDER BY transaction_id"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "txn_001"
        assert rows[0][2] == Decimal("1499.50")
        assert rows[0][3] == "DEBIT"
        assert rows[1][0] == "txn_002"
        assert rows[1][2] == Decimal("25000.00")
        assert rows[1][3] == "CREDIT"


def test_sync_is_idempotent(tmp_path, sample_silver_arrow_table):
    silver_path = tmp_path / "silver"
    db_path = tmp_path / "warehouse" / "finpulse.duckdb"

    write_deltalake(str(silver_path), sample_silver_arrow_table, mode="error")

    loader = WarehouseLoader(silver_path=silver_path, db_path=db_path)
    count1 = loader.sync()
    count2 = loader.sync()

    assert count1 == 2
    assert count2 == 2

    with duckdb.connect(str(db_path)) as con:
        total = con.execute("SELECT count(*) FROM silver.transactions").fetchone()[0]
        assert total == 2
