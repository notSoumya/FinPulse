import logging
import time

from finpulse.messaging.worker import KafkaTransactionWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main():
    worker = KafkaTransactionWorker()

    print("FinPulse Kafka worker started. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            result = worker.run_once()

            if result is None:
                time.sleep(0.2)
            else:
                logging.info("Worker result: %s", result)

    except KeyboardInterrupt:
        print("\nStopping FinPulse worker...")

    finally:
        worker.close()


if __name__ == "__main__":
    main()
