
import re
from datetime import datetime
from decimal import Decimal

from finpulse.common.hashing import generate_transaction_id
from finpulse.common.models import Transaction

AMOUNT_PATTERN = re.compile(
    r"(?:Rs\.?|INR)\s*([0-9,]+(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)

DEBIT_KEYWORDS = [
    "debited",
    "debit",
    "spent",
    "withdrawn",
]

CREDIT_KEYWORDS = [
    "credited",
    "credit",
    "received",
]


def extract_amount(message: str) -> Decimal:
    match = AMOUNT_PATTERN.search(message)

    if not match:
        raise ValueError("Transaction amount not found")

    return Decimal(match.group(1).replace(",", ""))


def extract_direction(message: str) -> str:
    text = message.lower()

    if any(keyword in text for keyword in DEBIT_KEYWORDS):
        return "DEBIT"

    if any(keyword in text for keyword in CREDIT_KEYWORDS):
        return "CREDIT"

    raise ValueError("Transaction direction not found")


def extract_merchant(message: str) -> str | None:
    patterns = [
        r"(?:at|towards|to)\s+([A-Za-z0-9 &._-]+)",
        r"from\s+([A-Za-z0-9 &._-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)

        if match:
            merchant = match.group(1).strip(" .")
            return merchant or None

    return None


def parse_bank_sms(
    message: str,
    user_id: str,
    timestamp: datetime,
    reference_id: str | None = None,
) -> Transaction:

    amount = extract_amount(message)

    direction = extract_direction(message)

    merchant = extract_merchant(message)

    transaction_id = generate_transaction_id(
        user_id=user_id,
        source_type="BANK_SMS",
        amount=amount,
        timestamp=timestamp,
        direction=direction,
        merchant=merchant,
        reference_id=reference_id,
    )

    return Transaction(
        transaction_id=transaction_id,
        user_id=user_id,
        amount=amount,
        currency="INR",
        direction=direction,
        transaction_timestamp=timestamp,
        merchant_raw=merchant,
        merchant_normalized=None,
        reference_id=reference_id,
        source_type="BANK_SMS",
    )