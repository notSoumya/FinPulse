from datetime import UTC, datetime
from decimal import Decimal

from finpulse.common.models import Transaction
from finpulse.processing.deduplicator import is_duplicate


def create_transaction(
    transaction_id,
    source_type,
    reference_id="REF123",
    merchant="Amazon",
    amount="500.00",
    timestamp=None,
    user_id="user_001",
):
    return Transaction(
        transaction_id=transaction_id,
        user_id=user_id,
        amount=Decimal(amount),
        currency="INR",
        direction="DEBIT",
        transaction_timestamp=timestamp or datetime(2026, 11, 9, 10, 30, tzinfo=UTC),
        merchant_normalized=merchant,
        reference_id=reference_id,
        source_type=source_type,
    )


def test_same_reference_id_is_duplicate():
    first = create_transaction("txn_001", "BANK_SMS")
    second = create_transaction("txn_002", "UPI_CSV")

    assert is_duplicate(first, second)


def test_different_reference_ids_can_match_heuristically():
    first = create_transaction("txn_001", "BANK_SMS", reference_id="REF001")
    second = create_transaction("txn_002", "UPI_CSV", reference_id="REF002")

    assert is_duplicate(first, second)


def test_different_users_are_not_duplicates():
    first = create_transaction("txn_001", "BANK_SMS")
    second = create_transaction("txn_002", "UPI_CSV", user_id="user_002")

    assert not is_duplicate(first, second)


def test_different_amounts_are_not_duplicates():
    first = create_transaction("txn_001", "BANK_SMS")
    second = create_transaction("txn_002", "UPI_CSV", amount="700.00")

    assert not is_duplicate(first, second)


def test_different_merchants_are_not_duplicates():
    first = create_transaction("txn_001", "BANK_SMS")
    second = create_transaction("txn_002", "UPI_CSV", merchant="Flipkart")

    assert not is_duplicate(first, second)


def test_timestamp_outside_tolerance_is_not_duplicate():
    first = create_transaction("txn_001", "BANK_SMS")
    second = create_transaction(
        "txn_002",
        "UPI_CSV",
        timestamp=datetime(2026, 11, 9, 10, 40, tzinfo=UTC),
    )

    assert not is_duplicate(first, second)


def test_same_source_different_ids_are_not_cross_source_duplicates():
    first = create_transaction("txn_001", "UPI_CSV")
    second = create_transaction("txn_002", "UPI_CSV")

    assert not is_duplicate(first, second)


def test_same_transaction_id_is_duplicate():
    first = create_transaction("txn_001", "UPI_CSV")
    second = create_transaction("txn_001", "UPI_CSV")

    assert is_duplicate(first, second)


def test_same_amount_and_merchant_without_normalized_merchant_is_not_duplicate():
    first = create_transaction("txn_001", "BANK_SMS", merchant=None)
    second = create_transaction("txn_002", "UPI_CSV", merchant=None)

    assert not is_duplicate(first, second)
