from datetime import UTC, datetime
from decimal import Decimal

from finpulse.common.hashing import (
    generate_payload_hash,
    generate_transaction_id,
)


def test_transaction_id_is_deterministic():
    args = (
        "user_001",
        "UPI_CSV",
        Decimal("500.00"),
        datetime(2026, 11, 7, tzinfo=UTC),
        "DEBIT",
    )

    id1 = generate_transaction_id(*args, merchant="Amazon")
    id2 = generate_transaction_id(*args, merchant="Amazon")

    assert id1 == id2


def test_different_reference_ids_produce_different_ids():
    common = (
        "user_001",
        "UPI_CSV",
        Decimal("500.00"),
        datetime(2026, 11, 7, tzinfo=UTC),
        "DEBIT",
    )

    id1 = generate_transaction_id(*common, reference_id="REF001")
    id2 = generate_transaction_id(*common, reference_id="REF002")

    assert id1 != id2


def test_payload_hash_is_deterministic():
    payload = {"amount": 500, "merchant": "Amazon"}

    hash1 = generate_payload_hash(payload)
    hash2 = generate_payload_hash(payload)

    assert hash1 == hash2


def test_payload_hash_ignores_dictionary_key_order():
    payload1 = {"amount": 500, "merchant": "Amazon"}
    payload2 = {"merchant": "Amazon", "amount": 500}

    assert generate_payload_hash(payload1) == generate_payload_hash(payload2)
