import json
from unittest.mock import MagicMock, patch

import pytest

from finpulse.messaging.dlq import DeadLetterProducer


@patch("finpulse.messaging.dlq.Producer")
def test_dlq_publishes_failed_event(mock_producer):
    mock_instance = MagicMock()
    mock_instance.flush.return_value = 0
    mock_producer.return_value = mock_instance

    dlq = DeadLetterProducer()

    event = {
        "event_id": "event_001",
        "event_type": "TRANSACTION_CREATED",
    }

    dlq_id = dlq.publish(
        source_type="MANUAL",
        original_event=event,
        error="Invalid transaction",
        original_topic="raw.manual",
    )

    assert dlq_id
    mock_instance.produce.assert_called_once()

    call_args = mock_instance.produce.call_args.kwargs
    assert call_args["topic"] == "dlq.manual"

    published_event = json.loads(call_args["value"].decode("utf-8"))
    assert published_event["original_event"] == event
    assert published_event["error"] == "Invalid transaction"
    assert published_event["original_topic"] == "raw.manual"


@patch("finpulse.messaging.dlq.Producer")
def test_dlq_rejects_unsupported_source_type(mock_producer):
    dlq = DeadLetterProducer()

    with pytest.raises(ValueError, match="Unsupported source type"):
        dlq.publish(
            source_type="UNKNOWN",
            original_event={},
            error="Test error",
            original_topic="raw.unknown",
        )

    mock_producer.return_value.produce.assert_not_called()


@patch("finpulse.messaging.dlq.Producer")
def test_dlq_raises_timeout_if_message_not_delivered(mock_producer):
    mock_instance = MagicMock()
    mock_instance.flush.return_value = 1
    mock_producer.return_value = mock_instance

    dlq = DeadLetterProducer()

    with pytest.raises(TimeoutError):
        dlq.publish(
            source_type="MANUAL",
            original_event={"event_id": "event_002"},
            error="Test timeout",
            original_topic="raw.manual",
        )


@patch("finpulse.messaging.dlq.Producer")
def test_dlq_closes_producer(mock_producer):
    mock_instance = MagicMock()
    mock_producer.return_value = mock_instance

    dlq = DeadLetterProducer()
    dlq.close()

    mock_instance.flush.assert_called_once_with(timeout=10)