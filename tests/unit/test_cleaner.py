
from datetime import UTC, datetime
from decimal import Decimal

from finpulse.common.models import Transaction
from finpulse.processing.cleaner import clean_transaction


def create_transaction():
    return Transaction(
        transaction_id="txn_001",
        user_id="user_001",
        amount=Decimal("500.00"),
        currency="inr",
        direction="DEBIT",
        transaction_timestamp=datetime(
            2026, 11, 9, 10, 30, tzinfo=UTC
        ),
        merchant_raw="  AMZN PAYMENTS  ",
        merchant_normalized="  Amazon  ",
        reference_id="  REF123  ",
        source_type="UPI_CSV",
    )


def test_cleaner_trims_merchant_names():
    transaction = create_transaction()

    cleaned = clean_transaction(transaction)

    assert cleaned.merchant_raw == "AMZN PAYMENTS"
    assert cleaned.merchant_normalized == "Amazon"


def test_cleaner_trims_reference_id():
    transaction = create_transaction()

    cleaned = clean_transaction(transaction)

    assert cleaned.reference_id == "REF123"


def test_cleaner_standardizes_currency():
    transaction = create_transaction()

    cleaned = clean_transaction(transaction)

    assert cleaned.currency == "INR"


def test_cleaner_preserves_decimal_amount():
    transaction = create_transaction()

    cleaned = clean_transaction(transaction)

    assert cleaned.amount == Decimal("500.00")
    assert isinstance(cleaned.amount, Decimal)


def test_cleaner_does_not_modify_original():
    transaction = create_transaction()

    clean_transaction(transaction)

    assert transaction.merchant_raw == "  AMZN PAYMENTS  "