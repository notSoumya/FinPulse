
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from finpulse.common.models import Transaction
from finpulse.messaging.producer import KafkaTransactionProducer


def create_transaction(source_type="UPI_CSV"):
    return Transaction(
        transaction_id="txn_001",
        user_id="user_001",
        amount=Decimal("500.00"),
        currency="INR",
        direction="DEBIT",
        transaction_timestamp=datetime(2026, 11, 7, tzinfo=UTC),
        merchant_raw="Amazon",
        source_type=source_type,
    )


@patch("finpulse.messaging.producer.Producer")
def test_producer_publishes_to_correct_topic(mock_producer):
    mock_instance = MagicMock()
    mock_instance.flush.return_value = 0
    mock_producer.return_value = mock_instance

    kafka_producer = KafkaTransactionProducer()

    transaction = create_transaction("UPI_CSV")
    event_id = kafka_producer.publish(transaction)

    assert event_id
    mock_instance.produce.assert_called_once()

    kwargs = mock_instance.produce.call_args.kwargs

    assert kwargs["topic"] == "raw.upi.csv"
    assert kwargs["key"] == "txn_001"


@patch("finpulse.messaging.producer.Producer")
def test_producer_flushes_message(mock_producer):
    mock_instance = MagicMock()
    mock_instance.flush.return_value = 0
    mock_producer.return_value = mock_instance

    kafka_producer = KafkaTransactionProducer()
    kafka_producer.publish(create_transaction())

    mock_instance.flush.assert_called_once_with(timeout=10)


@patch("finpulse.messaging.producer.Producer")
def test_producer_raises_when_delivery_is_pending(mock_producer):
    mock_instance = MagicMock()
    mock_instance.flush.return_value = 1
    mock_producer.return_value = mock_instance

    kafka_producer = KafkaTransactionProducer()

    with pytest.raises(TimeoutError):
        kafka_producer.publish(create_transaction())