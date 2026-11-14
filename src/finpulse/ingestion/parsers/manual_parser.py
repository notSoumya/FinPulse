from datetime import datetime
from decimal import Decimal

from finpulse.common.hashing import generate_transaction_id
from finpulse.common.models import Transaction


def parse_manual(payload: dict) -> Transaction:
    """
    Convert a manually supplied JSON transaction
    into the canonical FinPulse Transaction model.
    """

    data = dict(payload)

    amount = Decimal(str(data["amount"]))

    timestamp = datetime.fromisoformat(data["transaction_timestamp"].replace("Z", "+00:00"))

    direction = data["direction"].strip().upper()
    currency = data.get("currency", "INR").strip().upper()

    merchant = data.get("merchant_raw")
    reference_id = data.get("reference_id")

    transaction_id = data.get("transaction_id")

    if not transaction_id:
        transaction_id = generate_transaction_id(
            user_id=data["user_id"],
            source_type="MANUAL",
            amount=amount,
            timestamp=timestamp,
            direction=direction,
            merchant=merchant,
            reference_id=reference_id,
        )

    return Transaction(
        transaction_id=transaction_id,
        user_id=data["user_id"],
        amount=amount,
        currency=currency,
        direction=direction,
        transaction_timestamp=timestamp,
        merchant_raw=merchant,
        merchant_normalized=None,
        reference_id=reference_id,
        source_type="MANUAL",
    )
