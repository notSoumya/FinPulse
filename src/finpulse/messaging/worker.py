
import logging

from finpulse.messaging.consumer import KafkaTransactionConsumer
from finpulse.messaging.dlq import DeadLetterProducer
from finpulse.messaging.processor import process_event
from finpulse.messaging.retry import (
    RetryExhaustedError,
    execute_with_retry,
)

logger = logging.getLogger(__name__)


class KafkaTransactionWorker:
    def __init__(
        self,
        consumer=None,
        dlq_producer=None,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        self.consumer = consumer or KafkaTransactionConsumer()
        self.dlq_producer = dlq_producer or DeadLetterProducer()
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds

    def run_once(self) -> str | None:
        result = self.consumer.consume_message()

        if result is None:
            return None

        message, event = result

        try:
            transaction = execute_with_retry(
                lambda: process_event(event),
                max_attempts=self.max_attempts,
                delay_seconds=self.retry_delay_seconds,
            )

            logger.info(
                "Successfully processed transaction: %s",
                transaction.transaction_id,
            )

            self.consumer.commit(message)
            return "processed"

        except RetryExhaustedError as exc:
            logger.error(
                "Processing failed after retries. Sending event to DLQ."
            )

            payload = event.get("payload", {})
            source_type = payload.get("source_type")

            self.dlq_producer.publish(
                source_type=source_type,
                original_event=event,
                error=str(exc),
                original_topic=message.topic(),
            )

            # Commit only after the DLQ publish succeeds.
            self.consumer.commit(message)
            return "sent_to_dlq"

    def close(self):
        self.consumer.close()
        self.dlq_producer.close()