from finpulse.processing.validator import validate_transaction


def valid_transaction():
    return {
        "transaction_id": "txn_001",
        "user_id": "user_001",
        "amount": "500.00",
        "currency": "INR",
        "direction": "DEBIT",
        "transaction_timestamp": "2026-11-09T10:30:00Z",
        "merchant_raw": "AMZN PAYMENTS",
        "source_type": "UPI_CSV",
    }


def test_valid_transaction_is_accepted():
    transaction, errors = validate_transaction(valid_transaction())

    assert transaction is not None
    assert errors == []
    assert transaction.transaction_id == "txn_001"


def test_negative_amount_is_rejected():
    data = valid_transaction()
    data["amount"] = "-500"

    transaction, errors = validate_transaction(data)

    assert transaction is None
    assert len(errors) > 0


def test_missing_transaction_id_is_rejected():
    data = valid_transaction()
    del data["transaction_id"]

    transaction, errors = validate_transaction(data)

    assert transaction is None
    assert any("transaction_id" in error for error in errors)


def test_invalid_currency_is_rejected():
    data = valid_transaction()
    data["currency"] = "INVALID"

    transaction, errors = validate_transaction(data)

    assert transaction is None
    assert len(errors) > 0


def test_invalid_direction_is_rejected():
    data = valid_transaction()
    data["direction"] = "UNKNOWN"

    transaction, errors = validate_transaction(data)

    assert transaction is None
    assert len(errors) > 0


def test_missing_timestamp_is_rejected():
    data = valid_transaction()
    del data["transaction_timestamp"]

    transaction, errors = validate_transaction(data)

    assert transaction is None
    assert len(errors) > 0
