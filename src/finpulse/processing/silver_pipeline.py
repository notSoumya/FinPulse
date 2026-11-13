import logging
from datetime import UTC, datetime
from typing import Any

from finpulse.common.hashing import generate_payload_hash
from finpulse.common.models import SilverTransaction, Transaction
from finpulse.processing.bronze_reader import BronzeReader
from finpulse.processing.checkpoint import CheckpointManager
from finpulse.processing.cleaner import clean_transaction
from finpulse.processing.deduplicator import is_duplicate
from finpulse.processing.merchant_normalizer import MerchantNormalizer
from finpulse.processing.quarantine import QuarantineManager
from finpulse.processing.validator import validate_transaction
from finpulse.silver.writer import SilverWriter

logger = logging.getLogger(__name__)


class SilverPipeline:
    def __init__(
        self,
        bronze_reader: BronzeReader | None = None,
        merchant_normalizer: MerchantNormalizer | None = None,
        quarantine_manager: QuarantineManager | None = None,
        silver_writer: SilverWriter | None = None,
        checkpoint_manager: CheckpointManager | None = None,
    ):
        self.bronze_reader = bronze_reader or BronzeReader()
        self.merchant_normalizer = merchant_normalizer or MerchantNormalizer()
        self.quarantine_manager = quarantine_manager or QuarantineManager()
        self.silver_writer = silver_writer or SilverWriter()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()

    @staticmethod
    def _generate_deduplication_key(
        transaction: Transaction,
    ) -> str:
        fingerprint = {
            "user_id": transaction.user_id,
            "amount": str(transaction.amount),
            "currency": transaction.currency,
            "direction": transaction.direction,
            "transaction_timestamp": (transaction.transaction_timestamp.isoformat()),
            "merchant_normalized": (
                transaction.merchant_normalized.casefold()
                if transaction.merchant_normalized
                else None
            ),
            "reference_id": (
                transaction.reference_id.strip().upper() if transaction.reference_id else None
            ),
        }

        return generate_payload_hash(fingerprint)

    @staticmethod
    def _load_existing_transactions(
        records: list[dict[str, Any]],
    ) -> list[Transaction]:
        transactions = []
        transaction_fields = Transaction.model_fields.keys()

        for record in records:
            try:
                transactions.append(
                    Transaction.model_validate({key: record[key] for key in transaction_fields})
                )
            except (KeyError, ValueError):
                logger.exception("Could not load an existing Silver transaction")

        return transactions

    def run(self) -> dict[str, int]:
        stats = {
            "events_read": 0,
            "events_skipped_by_checkpoint": 0,
            "transactions_written": 0,
            "duplicates_skipped": 0,
            "transactions_quarantined": 0,
        }

        existing_transactions = self._load_existing_transactions(self.silver_writer.read_all())

        # Track event IDs encountered during this pipeline run.
        seen_event_ids: set[str] = set()

        for event in self.bronze_reader.read_events():
            stats["events_read"] += 1

            event_id = event.get("event_id")

            if not isinstance(event_id, str) or not event_id.strip():
                logger.error("Bronze event has no valid event_id; cannot checkpoint")
                self.quarantine_manager.quarantine_record(
                    event,
                    ["Missing or invalid event_id"],
                )
                stats["transactions_quarantined"] += 1
                continue

            # First detect repeated copies within this run.
            # This check must happen before the checkpoint check.
            if event_id in seen_event_ids:
                stats["duplicates_skipped"] += 1
                continue

            seen_event_ids.add(event_id)

            # Then skip events processed during earlier runs.
            if self.checkpoint_manager.is_processed(event_id):
                stats["events_skipped_by_checkpoint"] += 1
                continue

            # Ignore unsupported event types.
            if event.get("event_type") != "TRANSACTION_CREATED":
                self.checkpoint_manager.mark_processed(event_id)
                continue

            payload = event.get("payload")

            if not isinstance(payload, dict):
                self.quarantine_manager.quarantine_record(
                    event,
                    ["Missing or invalid transaction payload"],
                )
                self.checkpoint_manager.mark_processed(event_id)
                stats["transactions_quarantined"] += 1
                continue

            transaction, errors = validate_transaction(payload)

            if transaction is None:
                self.quarantine_manager.quarantine_record(
                    event,
                    errors,
                )
                self.checkpoint_manager.mark_processed(event_id)
                stats["transactions_quarantined"] += 1
                continue

            try:
                transaction = clean_transaction(transaction)

                transaction = self.merchant_normalizer.normalize_transaction(transaction)

                duplicate_found = any(
                    is_duplicate(transaction, existing) for existing in existing_transactions
                )

                if duplicate_found:
                    self.checkpoint_manager.mark_processed(event_id)
                    stats["duplicates_skipped"] += 1
                    continue

                deduplication_key = self._generate_deduplication_key(transaction)

                silver_transaction = SilverTransaction(
                    **transaction.model_dump(),
                    deduplication_key=deduplication_key,
                    processed_at=datetime.now(UTC),
                )

            except (ValueError, TypeError) as exc:
                logger.exception(
                    "Invalid transaction in Bronze event %s",
                    event_id,
                )

                self.quarantine_manager.quarantine_record(
                    event,
                    [f"Transaction processing error: {exc}"],
                )

                self.checkpoint_manager.mark_processed(event_id)
                stats["transactions_quarantined"] += 1
                continue

            written = self.silver_writer.write([silver_transaction])

            self.checkpoint_manager.mark_processed(event_id)

            stats["transactions_written"] += written

            existing_transactions.append(transaction)

        logger.info(
            "Silver pipeline completed: %s",
            stats,
        )

        return stats
