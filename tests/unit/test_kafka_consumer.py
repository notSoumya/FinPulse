import json
from unittest.mock import MagicMock, patch

from finpulse.messaging.consumer import KafkaTransactionConsumer


@patch("finpulse.messaging.consumer.Consumer")
def test_consumer_subscribes_to_all_topics(mock_consumer):
    KafkaTransactionConsumer()

    mock_consumer.return_value.subscribe.assert_called_once_with(
        [
            "raw.bank.sms",
            "raw.upi.csv",
            "raw.card.pdf",
            "raw.manual",
        ]
    )


@patch("finpulse.messaging.consumer.Consumer")
def test_consumer_reads_message(mock_consumer):
    mock_instance = MagicMock()
    mock_consumer.return_value = mock_instance

    message = MagicMock()
    message.error.return_value = None
    message.value.return_value = json.dumps(
        {
            "event_id": "event_001",
            "event_type": "TRANSACTION_CREATED",
        }
    ).encode("utf-8")

    mock_instance.poll.return_value = message

    consumer = KafkaTransactionConsumer()

    received_message, event = consumer.consume_message()

    assert received_message == message
    assert event["event_id"] == "event_001"


@patch("finpulse.messaging.consumer.Consumer")
def test_consumer_returns_none_when_no_message(mock_consumer):
    mock_instance = MagicMock()
    mock_instance.poll.return_value = None
    mock_consumer.return_value = mock_instance

    consumer = KafkaTransactionConsumer()

    assert consumer.consume_message() is None


@patch("finpulse.messaging.consumer.Consumer")
def test_consumer_commits_message(mock_consumer):
    mock_instance = MagicMock()
    mock_consumer.return_value = mock_instance

    consumer = KafkaTransactionConsumer()
    message = MagicMock()

    consumer.commit(message)

    mock_instance.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )


@patch("finpulse.messaging.consumer.Consumer")
def test_consumer_closes(mock_consumer):
    mock_instance = MagicMock()
    mock_consumer.return_value = mock_instance

    consumer = KafkaTransactionConsumer()
    consumer.close()

    mock_instance.close.assert_called_once()
