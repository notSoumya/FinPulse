
from datetime import timedelta

from finpulse.common.models import Transaction


def is_duplicate(
    first: Transaction,
    second: Transaction,
    timestamp_tolerance_minutes: int = 5,
) -> bool:
    """
    Check whether two transactions from different sources
    represent the same payment.
    """

    if first.transaction_id == second.transaction_id:
        return True

    if first.user_id != second.user_id:
        return False

    if first.source_type == second.source_type:
        return False

    # These core fields must match for either matching strategy.
    if first.amount != second.amount:
        return False

    if first.currency != second.currency:
        return False

    if first.direction != second.direction:
        return False

    # A reference ID is a strong signal, but verify the
    # merchant and timestamp when those details are available.
    if first.reference_id and second.reference_id:
        if first.reference_id == second.reference_id:
            if not first.merchant_normalized or not second.merchant_normalized:
                return False

            if (
                first.merchant_normalized.casefold()
                != second.merchant_normalized.casefold()
            ):
                return False

            time_difference = abs(
                first.transaction_timestamp
                - second.transaction_timestamp
            )

            return time_difference <= timedelta(
                minutes=timestamp_tolerance_minutes
            )

    # Without a matching reference ID, use a conservative
    # heuristic match.
    if not first.merchant_normalized or not second.merchant_normalized:
        return False

    if (
        first.merchant_normalized.casefold()
        != second.merchant_normalized.casefold()
    ):
        return False

    time_difference = abs(
        first.transaction_timestamp - second.transaction_timestamp
    )

    return time_difference <= timedelta(
        minutes=timestamp_tolerance_minutes
    )