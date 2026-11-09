
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from confluent_kafka import Producer

from finpulse.common.constants import TOPICS
from finpulse.common.models import Transaction

logger = logging.getLogger(__name__)


class KafkaTransactionProducer:
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "client.id": "finpulse-ingestion-producer",
            "acks": "all",
        })

    def delivery_report(self, err, message):
        if err is not None:
            logger.error("Kafka delivery failed: %s", err)
        else:
            logger.info(
                "Transaction delivered to %s [%s] at offset %s",
                message.topic(),
                message.partition(),
                message.offset(),
            )

    def publish(self, transaction: Transaction) -> str:
        topic = TOPICS[transaction.source_type]

        event = {
            "event_id": str(uuid4()),
            "event_timestamp": datetime.now(UTC).isoformat(),
            "schema_version": "1.0",
            "event_type": "TRANSACTION_CREATED",
            "payload": transaction.model_dump(mode="json"),
        }

        event_json = json.dumps(event)

        try:
            self.producer.produce(
                topic=topic,
                key=transaction.transaction_id,
                value=event_json.encode("utf-8"),
                callback=self.delivery_report,
            )

            remaining = self.producer.flush(timeout=10)

            if remaining > 0:
                raise TimeoutError(
                    f"{remaining} Kafka message(s) still pending delivery"
                )

        except Exception:
            logger.exception("Failed to publish transaction")
            raise

        return event["event_id"]

    def close(self):
        self.producer.flush(timeout=10)
    