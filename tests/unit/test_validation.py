
from datetime import UTC, datetime
from decimal import Decimal

from finpulse.ingestion.validation import (
    validate_transaction,
    validate_transactions,
)


def valid_record():
    return {
        "transaction_id": "txn_001",
        "user_id": "user_001",
        "amount": Decimal("500.00"),
        "currency": "INR",
        "direction": "DEBIT",
        "transaction_timestamp": datetime.now(UTC),
        "merchant_raw": "Amazon",
        "source_type": "MANUAL",
    }


def test_valid_transaction():
    transaction = validate_transaction(valid_record())

    assert transaction.transaction_id == "txn_001"
    assert transaction.amount == Decimal("500.00")


def test_invalid_transaction_rejected():
    record = valid_record()
    record["amount"] = -100

    valid, rejected = validate_transactions([record])

    assert len(valid) == 0
    assert len(rejected) == 1
    assert rejected[0]["record_index"] == 0


def test_mixed_valid_and_invalid_transactions():
    valid = valid_record()
    invalid = valid_record()
    invalid["direction"] = "UNKNOWN"

    accepted, rejected = validate_transactions([valid, invalid])

    assert len(accepted) == 1
    assert len(rejected) == 1


def test_empty_input():
    valid, rejected = validate_transactions([])

    assert valid == []
    assert rejected == []