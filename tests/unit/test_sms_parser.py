from datetime import UTC, datetime
from decimal import Decimal

import pytest

from finpulse.ingestion.parsers.sms_parser import parse_bank_sms


def test_debit_sms():
    message = "Rs. 500.00 debited from your account at AMAZON."

    transaction = parse_bank_sms(
        message,
        "user_001",
        datetime(2026, 11, 7, tzinfo=UTC),
    )

    assert transaction.amount == Decimal("500.00")
    assert transaction.direction == "DEBIT"
    assert transaction.source_type == "BANK_SMS"


def test_credit_sms():
    message = "INR 1,200.00 credited to your account from SALARY."

    transaction = parse_bank_sms(
        message,
        "user_001",
        datetime(2026, 11, 7, tzinfo=UTC),
    )

    assert transaction.amount == Decimal("1200.00")
    assert transaction.direction == "CREDIT"


def test_sms_without_amount():
    message = "Your account has been debited."

    with pytest.raises(ValueError, match="Transaction amount not found"):
        parse_bank_sms(
            message,
            "user_001",
            datetime.now(UTC),
        )


def test_sms_without_direction():
    message = "Rs. 500.00 transaction at AMAZON."

    with pytest.raises(ValueError, match="Transaction direction not found"):
        parse_bank_sms(
            message,
            "user_001",
            datetime.now(UTC),
        )
