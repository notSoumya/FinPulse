
from decimal import Decimal

from finpulse.ingestion.parsers.manual_parser import parse_manual


def test_manual_parser():
    payload = {
        "user_id": "user_001",
        "amount": "500.00",
        "currency": "INR",
        "direction": "DEBIT",
        "transaction_timestamp": "2026-11-07T12:30:00+05:30",
        "merchant_raw": "Amazon",
        "reference_id": "REF123",
    }

    transaction = parse_manual(payload)

    assert transaction.amount == Decimal("500.00")
    assert transaction.direction == "DEBIT"
    assert transaction.source_type == "MANUAL"
    assert transaction.merchant_raw == "Amazon"
    assert transaction.transaction_id


def test_manual_parser_generates_same_id_for_same_input():
    payload = {
        "user_id": "user_001",
        "amount": "500",
        "direction": "DEBIT",
        "transaction_timestamp": "2026-11-07T12:30:00+05:30",
    }

    tx1 = parse_manual(payload)
    tx2 = parse_manual(payload)

    assert tx1.transaction_id == tx2.transaction_id