
from typing import Any

from pydantic import ValidationError

from finpulse.common.models import Transaction


def validate_transaction(
    raw_data: dict[str, Any],
) -> tuple[Transaction | None, list[str]]:
    """
    Validate raw transaction data.

    Returns:
        (Transaction, []) when valid.
        (None, rejection_reasons) when invalid.
    """
    try:
        transaction = Transaction.model_validate(raw_data)
        return transaction, []

    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(part) for part in error['loc'])}: "
            f"{error['msg']}"
            for error in exc.errors()
        ]

        return None, errors