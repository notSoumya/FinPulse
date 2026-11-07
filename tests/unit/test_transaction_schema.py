
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from finpulse.common.models import Transaction


def sample_transaction():
    return {
        "transaction_id": "txn_001",
        "user_id": "user_001",
        "amount": Decimal("500.00"),
        "currency": "INR",
        "direction": "DEBIT",
        "transaction_timestamp": datetime.now(timezone.utc),
        "merchant_raw": "Amazon Pay",
        "merchant_normalized": "AMAZON PAY",
        "reference_id": "REF12345",
        "source_type": "UPI_CSV",
    }


def test_valid_transaction():
    transaction = Transaction(**sample_transaction())

    assert transaction.amount == Decimal("500.00")
    assert transaction.direction == "DEBIT"


def test_negative_amount_rejected():
    data = sample_transaction()
    data["amount"] = Decimal("-100")

    with pytest.raises(ValidationError):
        Transaction(**data)


def test_invalid_direction_rejected():
    data = sample_transaction()
    data["direction"] = "TRANSFER"

    with pytest.raises(ValidationError):
        Transaction(**data)


def test_invalid_source_rejected():
    data = sample_transaction()
    data["source_type"] = "UNKNOWN"

    with pytest.raises(ValidationError):
        Transaction(**data)


def test_timezone_is_required():
    data = sample_transaction()
    data["transaction_timestamp"] = datetime(2026, 11, 7)

    with pytest.raises(ValidationError):
        Transaction(**data)


def test_timestamp_converted_to_utc():
    transaction = Transaction(**sample_transaction())

    assert transaction.transaction_timestamp.utcoffset().total_seconds() == 0


def test_currency_normalization():
    data = sample_transaction()
    data["currency"] = "inr"

    transaction = Transaction(**data)

    assert transaction.currency == "INR"
