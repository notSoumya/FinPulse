from decimal import Decimal

import pandas as pd

from finpulse.common.hashing import generate_transaction_id
from finpulse.common.models import Transaction


def parse_upi_csv(file_path: str, user_id: str) -> list[Transaction]:
    """
    Parse a UPI CSV statement into canonical Transaction objects.
    """

    df = pd.read_csv(file_path)

    required_columns = {
        "date",
        "amount",
        "type",
        "merchant",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    transactions = []

    for row in df.to_dict(orient="records"):
        amount = Decimal(str(row["amount"]))

        raw_type = str(row["type"]).strip().upper()

        direction_mapping = {
            "DR": "DEBIT",
            "DEBIT": "DEBIT",
            "CR": "CREDIT",
            "CREDIT": "CREDIT",
        }

        if raw_type not in direction_mapping:
            raise ValueError(f"Invalid transaction type: {raw_type}")

        direction = direction_mapping[raw_type]

        timestamp = pd.to_datetime(
            row["date"],
            utc=True,
            errors="raise",
        ).to_pydatetime()

        merchant = str(row["merchant"]).strip()

        reference_id = row.get("reference_id")

        if pd.isna(reference_id):
            reference_id = None
        else:
            reference_id = str(reference_id).strip() or None

        currency = row.get("currency", "INR")

        if pd.isna(currency):
            currency = "INR"

        currency = str(currency).strip().upper()

        transaction_id = generate_transaction_id(
            user_id=user_id,
            source_type="UPI_CSV",
            amount=amount,
            timestamp=timestamp,
            direction=direction,
            merchant=merchant,
            reference_id=reference_id,
        )

        transaction = Transaction(
            transaction_id=transaction_id,
            user_id=user_id,
            amount=amount,
            currency=currency,
            direction=direction,
            transaction_timestamp=timestamp,
            merchant_raw=merchant,
            merchant_normalized=None,
            reference_id=reference_id,
            source_type="UPI_CSV",
        )

        transactions.append(transaction)

    return transactions
