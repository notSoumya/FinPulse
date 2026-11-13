from pydantic import ValidationError

from finpulse.common.models import Transaction


def validate_transaction(data: dict) -> Transaction:
    """
    Validate incoming transaction data against the shared schema.

    Raises ValidationError if the transaction is invalid.
    """
    return Transaction.model_validate(data)


def validate_transactions(data: list[dict]) -> tuple[list[Transaction], list[dict]]:
    """
    Validate multiple transactions.

    Returns:
        valid: Successfully validated transactions.
        rejected: Invalid records with their error details.
    """
    valid = []
    rejected = []

    for index, record in enumerate(data):
        try:
            transaction = validate_transaction(record)
            valid.append(transaction)

        except (ValidationError, ValueError, TypeError) as exc:
            rejected.append(
                {
                    "record_index": index,
                    "reason": str(exc),
                    "record": record,
                }
            )

    return valid, rejected
