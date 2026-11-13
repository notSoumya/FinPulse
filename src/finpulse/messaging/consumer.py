import json
import logging

from confluent_kafka import Consumer, KafkaException

logger = logging.getLogger(__name__)


class KafkaTransactionConsumer:
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "finpulse-consumer-group",
        topics: list[str] | None = None,
    ):
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )

        self.topics = topics or [
            "raw.bank.sms",
            "raw.upi.csv",
            "raw.card.pdf",
            "raw.manual",
        ]

        self.consumer.subscribe(self.topics)

    def consume_message(self, timeout: float = 1.0):
        message = self.consumer.poll(timeout)

        if message is None:
            return None

        if message.error():
            raise KafkaException(message.error())

        try:
            event = json.loads(message.value().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.exception("Invalid Kafka event received")
            raise

        return message, event

    def commit(self, message):
        self.consumer.commit(
            message=message,
            asynchronous=False,
        )

    def close(self):
        self.consumer.close()
