
from datetime import UTC, datetime
from decimal import Decimal

from finpulse.common.models import SilverTransaction
from finpulse.silver.writer import SilverWriter


def create_silver_transaction(
    transaction_id="txn_001",
):
    return SilverTransaction(
        transaction_id=transaction_id,
        user_id="user_001",
        amount=Decimal("500.00"),
        currency="INR",
        direction="DEBIT",
        transaction_timestamp=datetime(
            2026, 11, 9, 10, 30, tzinfo=UTC
        ),
        merchant_raw="AMZN PAYMENTS",
        merchant_normalized="Amazon",
        reference_id="REF123",
        source_type="BANK_SMS",
        deduplication_key=f"hash_{transaction_id}",
        processed_at=datetime.now(UTC),
    )


def test_write_single_transaction(tmp_path):
    writer = SilverWriter(tmp_path / "silver")

    count = writer.write([create_silver_transaction()])

    assert count == 1
    assert len(writer.read_all()) == 1


def test_write_multiple_transactions(tmp_path):
    writer = SilverWriter(tmp_path / "silver")

    transactions = [
        create_silver_transaction("txn_001"),
        create_silver_transaction("txn_002"),
    ]

    count = writer.write(transactions)

    assert count == 2
    assert len(writer.read_all()) == 2


def test_empty_write_does_nothing(tmp_path):
    writer = SilverWriter(tmp_path / "silver")

    count = writer.write([])

    assert count == 0
    assert writer.read_all() == []


def test_append_preserves_existing_records(tmp_path):
    writer = SilverWriter(tmp_path / "silver")

    writer.write([create_silver_transaction("txn_001")])
    writer.write([create_silver_transaction("txn_002")])

    records = writer.read_all()

    assert len(records) == 2
    assert {record["transaction_id"] for record in records} == {
        "txn_001",
        "txn_002",
    }

def test_duplicate_deduplication_key_is_not_inserted_again(tmp_path):
    writer = SilverWriter(tmp_path / "silver")

    transaction = create_silver_transaction("txn_001")

    first_count = writer.write([transaction])
    second_count = writer.write([transaction])

    assert first_count == 1
    assert second_count == 0
    assert len(writer.read_all()) == 1


def test_duplicate_keys_in_same_batch_are_inserted_once(tmp_path):
    writer = SilverWriter(tmp_path / "silver")

    first = create_silver_transaction("txn_001")
    second = create_silver_transaction("txn_001")

    count = writer.write([first, second])

    assert count == 1
    assert len(writer.read_all()) == 1