
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from finpulse.common.models import SilverTransaction


def valid_silver_transaction():
    return {
        "transaction_id": "txn_001",
        "user_id": "user_001",
        "amount": Decimal("500.00"),
        "currency": "inr",
        "direction": "DEBIT",
        "transaction_timestamp": datetime(
            2026, 11, 9, 10, 30, tzinfo=UTC
        ),
        "merchant_raw": "AMZN PAYMENTS",
        "merchant_normalized": "Amazon",
        "reference_id": "REF123",
        "source_type": "UPI_CSV",
        "deduplication_key": "dedup_001",
        "processed_at": datetime.now(UTC),
    }


# Test 1: Valid Silver transaction
def test_valid_silver_transaction():
    transaction = SilverTransaction(**valid_silver_transaction())

    assert transaction.amount == Decimal("500.00")
    assert transaction.currency == "INR"
    assert transaction.merchant_normalized == "Amazon"


# Test 2: Deduplication key is required
def test_deduplication_key_is_required():
    data = valid_silver_transaction()
    del data["deduplication_key"]

    with pytest.raises(ValidationError):
        SilverTransaction(**data)


# Test 3: processed_at requires timezone
def test_processed_at_requires_timezone():
    data = valid_silver_transaction()
    data["processed_at"] = datetime(2026, 11, 9, 10, 30)

    with pytest.raises(ValidationError):
        SilverTransaction(**data)


# Test 4: processed_at is converted to UTC
def test_processed_at_is_converted_to_utc():
    data = valid_silver_transaction()
    data["processed_at"] = datetime.fromisoformat(
        "2026-11-09T16:00:00+05:30"
    )

    transaction = SilverTransaction(**data)

    assert transaction.processed_at.utcoffset().total_seconds() == 0
