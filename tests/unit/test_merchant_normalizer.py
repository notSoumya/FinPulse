import json
from datetime import UTC, datetime
from decimal import Decimal

from finpulse.common.models import Transaction
from finpulse.processing.merchant_normalizer import MerchantNormalizer


def create_normalizer(tmp_path):
    mapping_path = tmp_path / "merchant_mapping.json"

    mapping_path.write_text(
        json.dumps(
            {
                "AMZN PAYMENTS": "Amazon",
                "AMAZON INDIA": "Amazon",
                "UBER INDIA": "Uber",
            }
        ),
        encoding="utf-8",
    )

    return MerchantNormalizer(mapping_path)


def test_normalizes_known_merchant(tmp_path):
    normalizer = create_normalizer(tmp_path)

    assert normalizer.normalize("AMZN PAYMENTS") == "Amazon"


def test_normalization_is_case_insensitive(tmp_path):
    normalizer = create_normalizer(tmp_path)

    assert normalizer.normalize("amazon india") == "Amazon"


def test_normalizes_extra_whitespace(tmp_path):
    normalizer = create_normalizer(tmp_path)

    assert normalizer.normalize("  UBER   INDIA  ") == "Uber"


def test_preserves_unknown_merchant(tmp_path):
    normalizer = create_normalizer(tmp_path)

    assert normalizer.normalize("LOCAL GROCERY STORE") == ("Local Grocery Store")


def test_none_merchant_returns_none(tmp_path):
    normalizer = create_normalizer(tmp_path)

    assert normalizer.normalize(None) is None


def test_empty_merchant_returns_none(tmp_path):
    normalizer = create_normalizer(tmp_path)

    assert normalizer.normalize("   ") is None


def test_normalizes_transaction_without_modifying_original(tmp_path):
    normalizer = create_normalizer(tmp_path)

    transaction = Transaction(
        transaction_id="txn_001",
        user_id="user_001",
        amount=Decimal("500.00"),
        currency="INR",
        direction="DEBIT",
        transaction_timestamp=datetime(2026, 11, 9, 10, 30, tzinfo=UTC),
        merchant_raw="AMZN PAYMENTS",
        source_type="UPI_CSV",
    )

    normalized = normalizer.normalize_transaction(transaction)

    assert normalized.merchant_normalized == "Amazon"
    assert transaction.merchant_normalized is None


def test_missing_mapping_file_raises_error(tmp_path):
    missing_path = tmp_path / "missing.json"

    try:
        MerchantNormalizer(missing_path)
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass
