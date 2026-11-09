import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from confluent_kafka import Producer

from finpulse.common.constants import DLQ_TOPICS

logger = logging.getLogger(__name__)


class DeadLetterProducer:
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "client.id": "finpulse-dlq-producer",
            "acks": "all",
        })

    def publish(
        self,
        source_type: str,
        original_event: dict,
        error: str,
        original_topic: str,
    ) -> str:
        if source_type not in DLQ_TOPICS:
            raise ValueError(f"Unsupported source type: {source_type}")

        dlq_event = {
            "dlq_event_id": str(uuid4()),
            "failed_at": datetime.now(UTC).isoformat(),
            "original_topic": original_topic,
            "source_type": source_type,
            "error": error,
            "original_event": original_event,
        }

        try:
            self.producer.produce(
                topic=DLQ_TOPICS[source_type],
                key=dlq_event["dlq_event_id"],
                value=json.dumps(dlq_event).encode("utf-8"),
            )

            remaining = self.producer.flush(timeout=10)

            if remaining > 0:
                raise TimeoutError(
                    f"{remaining} DLQ message(s) still pending delivery"
                )

            logger.info("Message sent to DLQ topic: %s", DLQ_TOPICS[source_type])

        except Exception:
            logger.exception("Failed to publish message to DLQ")
            raise

        return dlq_event["dlq_event_id"]

    def close(self):
        self.producer.flush(timeout=10)