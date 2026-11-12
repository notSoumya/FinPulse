
from finpulse.common.models import Transaction


def clean_transaction(transaction: Transaction) -> Transaction:
    """
    Clean and standardize transaction fields.

    Returns a new Transaction without modifying the original.
    """
    data = transaction.model_dump()

    if data["merchant_raw"]:
        data["merchant_raw"] = data["merchant_raw"].strip()

    if data["merchant_normalized"]:
        data["merchant_normalized"] = data["merchant_normalized"].strip()

    if data["reference_id"]:
        data["reference_id"] = data["reference_id"].strip()

    data["currency"] = data["currency"].strip().upper()

    return Transaction.model_validate(data)