import logging
import time

from confluent_kafka.admin import AdminClient, NewTopic

from finpulse.common.constants import DLQ_TOPICS, TOPICS

BOOTSTRAP_SERVERS = "localhost:9092"
NUM_PARTITIONS = 3
REPLICATION_FACTOR = 1
MAX_ATTEMPTS = 10
RETRY_DELAY = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def create_topics():
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})

    topic_names = list(dict.fromkeys(list(TOPICS.values()) + list(DLQ_TOPICS.values())))

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info(
                "Connecting to Kafka (attempt %s/%s)",
                attempt,
                MAX_ATTEMPTS,
            )

            # Fetch existing topics from Kafka
            metadata = admin.list_topics(timeout=10)
            existing_topics = set(metadata.topics.keys())

            # Identify only missing topics
            missing_topics = [topic for topic in topic_names if topic not in existing_topics]

            if not missing_topics:
                logger.info("All 8 Kafka topics already exist.")
                logger.info("Kafka topic initialization completed.")
                return

            logger.info("Creating %s missing topics.", len(missing_topics))

            new_topics = [
                NewTopic(
                    topic,
                    num_partitions=NUM_PARTITIONS,
                    replication_factor=REPLICATION_FACTOR,
                )
                for topic in missing_topics
            ]

            futures = admin.create_topics(new_topics)

            failed_topics = []

            for topic, future in futures.items():
                try:
                    future.result(timeout=15)
                    logger.info("Created topic: %s", topic)

                except Exception as exc:
                    logger.error("Failed to create %s: %s", topic, exc)
                    failed_topics.append(topic)

            if not failed_topics:
                logger.info("Kafka topic initialization completed.")
                return

        except Exception as exc:
            logger.warning("Kafka connection failed: %s", exc)

        if attempt < MAX_ATTEMPTS:
            logger.info("Retrying in %s seconds...", RETRY_DELAY)
            time.sleep(RETRY_DELAY)

    raise RuntimeError("Kafka topic initialization failed after all retry attempts.")


if __name__ == "__main__":
    create_topics()
