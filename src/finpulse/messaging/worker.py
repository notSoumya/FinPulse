
import logging

from finpulse.bronze.storage import BronzeStorage
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
        bronze_storage=None,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        self.consumer = (
            consumer if consumer is not None else KafkaTransactionConsumer()
        )
        self.dlq_producer = (
            dlq_producer if dlq_producer is not None else DeadLetterProducer()
        )
        self.bronze_storage = (
            bronze_storage if bronze_storage is not None else BronzeStorage()
        )
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds

    def run_once(self) -> str | None:
        result = self.consumer.consume_message()

        if result is None:
            return None

        message, event = result

        # Stage 1: Validate and process the event.
        try:
            transaction = execute_with_retry(
                lambda: process_event(event),
                max_attempts=self.max_attempts,
                delay_seconds=self.retry_delay_seconds,
            )

        except RetryExhaustedError as exc:
            logger.error(
                "Transaction validation failed after retries. Sending to DLQ."
            )

            payload = event.get("payload", {})
            source_type = (
                payload.get("source_type")
                if isinstance(payload, dict)
                else None
            )

            self.dlq_producer.publish(
                source_type=source_type,
                original_event=event,
                error=str(exc),
                original_topic=message.topic(),
            )

            # Commit only after successful DLQ publishing.
            self.consumer.commit(message)
            return "sent_to_dlq"

        # Stage 2: Persist the original event in Bronze.
        try:
            execute_with_retry(
                lambda: self.bronze_storage.write_event(event),
                max_attempts=self.max_attempts,
                delay_seconds=self.retry_delay_seconds,
            )

        except RetryExhaustedError:
            logger.exception(
                "Bronze storage failed after retries. "
                "Kafka offset will not be committed."
            )
            raise

        logger.info(
            "Successfully processed and stored transaction: %s",
            transaction.transaction_id,
        )

        # Stage 3: Commit only after Bronze persistence succeeds.
        self.consumer.commit(message)
        return "processed"

    def close(self):
        self.consumer.close()
        self.dlq_producer.close()
