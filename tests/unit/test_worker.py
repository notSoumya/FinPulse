
from unittest.mock import MagicMock, patch

import pytest

from finpulse.messaging.retry import RetryExhaustedError
from finpulse.messaging.worker import KafkaTransactionWorker


@pytest.fixture
def mock_dependencies():
    consumer = MagicMock()
    dlq = MagicMock()
    message = MagicMock()
    message.topic.return_value = "raw.manual"

    consumer.consume_message.return_value = (
        message,
        {
            "event_id": "event_001",
            "payload": {"source_type": "MANUAL"},
        },
    )

    return consumer, dlq, message


@patch("finpulse.messaging.worker.process_event")
def test_worker_processes_and_commits(
    mock_process, mock_dependencies
):
    consumer, dlq, message = mock_dependencies
    transaction = MagicMock()
    transaction.transaction_id = "txn_001"
    mock_process.return_value = transaction

    worker = KafkaTransactionWorker(
        consumer=consumer,
        dlq_producer=dlq,
        retry_delay_seconds=0,
    )

    result = worker.run_once()

    assert result == "processed"
    consumer.commit.assert_called_once_with(message)
    dlq.publish.assert_not_called()


@patch("finpulse.messaging.worker.execute_with_retry")
def test_worker_sends_exhausted_event_to_dlq(
    mock_retry, mock_dependencies
):
    consumer, dlq, message = mock_dependencies
    mock_retry.side_effect = RetryExhaustedError("Processing failed")

    worker = KafkaTransactionWorker(
        consumer=consumer,
        dlq_producer=dlq,
    )

    result = worker.run_once()

    assert result == "sent_to_dlq"
    dlq.publish.assert_called_once()
    consumer.commit.assert_called_once_with(message)


@patch("finpulse.messaging.worker.execute_with_retry")
def test_worker_does_not_commit_if_dlq_publish_fails(
    mock_retry, mock_dependencies
):
    consumer, dlq, message = mock_dependencies
    mock_retry.side_effect = RetryExhaustedError("Processing failed")
    dlq.publish.side_effect = RuntimeError("Kafka DLQ unavailable")

    worker = KafkaTransactionWorker(
        consumer=consumer,
        dlq_producer=dlq,
    )

    with pytest.raises(RuntimeError, match="Kafka DLQ unavailable"):
        worker.run_once()

    consumer.commit.assert_not_called()


def test_worker_returns_none_when_no_message(mock_dependencies):
    consumer, dlq, _ = mock_dependencies
    consumer.consume_message.return_value = None

    worker = KafkaTransactionWorker(
        consumer=consumer,
        dlq_producer=dlq,
    )

    assert worker.run_once() is None


def test_worker_closes_dependencies(mock_dependencies):
    consumer, dlq, _ = mock_dependencies

    worker = KafkaTransactionWorker(
        consumer=consumer,
        dlq_producer=dlq,
    )

    worker.close()

    consumer.close.assert_called_once()
    dlq.close.assert_called_once()