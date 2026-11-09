from datetime import UTC, datetime
from decimal import Decimal

import pytest

from finpulse.common.models import Transaction
from finpulse.messaging.processor import process_event


@pytest.fixture
def valid_event():
    return {
        "event_id": "event_001",
        "event_timestamp": datetime.now(UTC).isoformat(),
        "schema_version": "1.0",
        "event_type": "TRANSACTION_CREATED",
        "payload": {
            "transaction_id": "txn_001",
            "user_id": "user_001",
            "amount": "500.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": datetime.now(UTC).isoformat(),
            "merchant_raw": "Amazon",
            "source_type": "MANUAL",
        },
    }


def test_process_valid_event(valid_event):
    transaction = process_event(valid_event)

    assert isinstance(transaction, Transaction)
    assert transaction.transaction_id == "txn_001"
    assert transaction.amount == Decimal("500.00")


def test_process_event_rejects_missing_fields(valid_event):
    del valid_event["event_id"]

    with pytest.raises(ValueError, match="missing fields"):
        process_event(valid_event)


def test_process_event_rejects_unsupported_type(valid_event):
    valid_event["event_type"] = "UNKNOWN"

    with pytest.raises(ValueError, match="Unsupported event type"):
        process_event(valid_event)


def test_process_event_rejects_invalid_transaction(valid_event):
    valid_event["payload"]["amount"] = "-100"

    with pytest.raises(ValueError):
        process_event(valid_event)