
import hashlib
import json
from datetime import datetime
from decimal import Decimal


def generate_transaction_id(
    user_id: str,
    source_type: str,
    amount: Decimal,
    timestamp: datetime,
    direction: str,
    merchant: str | None = None,
    reference_id: str | None = None,
) -> str:
    """
    Generate a deterministic transaction ID.

    If a source reference ID exists, use it.
    Otherwise, create an ID from transaction attributes.
    """

    if reference_id:
        raw_data = (
            f"{user_id}|{source_type}|{reference_id.strip().upper()}"
        )
    else:
        raw_data = "|".join([
            user_id,
            source_type,
            str(amount),
            timestamp.isoformat(),
            direction,
            (merchant or "").strip().lower(),
        ])

    return hashlib.sha256(
        raw_data.encode("utf-8")
    ).hexdigest()


def generate_payload_hash(payload: dict) -> str:
    """
    Generate SHA-256 hash of a JSON payload.
    Useful for checking whether payloads are identical.
    """

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()
