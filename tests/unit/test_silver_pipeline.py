import json
from datetime import UTC, datetime
from decimal import Decimal

from finpulse.processing.bronze_reader import BronzeReader
from finpulse.processing.checkpoint import CheckpointManager
from finpulse.processing.merchant_normalizer import MerchantNormalizer
from finpulse.processing.quarantine import QuarantineManager
from finpulse.processing.silver_pipeline import SilverPipeline
from finpulse.silver.writer import SilverWriter


def create_event(
    transaction_id="txn_001",
    amount="2450.75",
    merchant="Flipkart",
):
    return {
        "event_id": f"event_{transaction_id}",
        "event_timestamp": datetime.now(UTC).isoformat(),
        "schema_version": "1.0",
        "event_type": "TRANSACTION_CREATED",
        "payload": {
            "transaction_id": transaction_id,
            "user_id": "test_user",
            "amount": amount,
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-11-09T10:30:00Z",
            "merchant_raw": merchant,
            "merchant_normalized": None,
            "reference_id": None,
            "source_type": "MANUAL",
        },
    }


def write_event(path, event):
    path.mkdir(parents=True, exist_ok=True)

    with (path / "events.jsonl").open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(json.dumps(event) + "\n")


def create_pipeline(tmp_path):
    bronze_path = tmp_path / "bronze"
    silver_path = tmp_path / "silver"
    quarantine_path = tmp_path / "quarantine"

    mapping_path = tmp_path / "merchant_mapping.json"
    mapping_path.write_text(
        json.dumps({"FLIPKART": "Flipkart"}),
        encoding="utf-8",
    )

    pipeline = SilverPipeline(
        bronze_reader=BronzeReader(bronze_path),
        merchant_normalizer=MerchantNormalizer(mapping_path),
        quarantine_manager=QuarantineManager(quarantine_path),
        silver_writer=SilverWriter(silver_path),
        checkpoint_manager=CheckpointManager(tmp_path / "checkpoint.json"),
    )

    return pipeline, bronze_path, silver_path, quarantine_path


def test_valid_event_is_written_to_silver(tmp_path):
    pipeline, bronze_path, silver_path, _ = create_pipeline(tmp_path)

    write_event(bronze_path, create_event())

    stats = pipeline.run()

    records = SilverWriter(silver_path).read_all()

    assert stats["events_read"] == 1
    assert stats["transactions_written"] == 1
    assert stats["transactions_quarantined"] == 0
    assert len(records) == 1
    assert records[0]["merchant_normalized"] == "Flipkart"
    assert Decimal(str(records[0]["amount"])) == Decimal("2450.75")


def test_invalid_event_is_quarantined(tmp_path):
    pipeline, bronze_path, silver_path, quarantine_path = create_pipeline(tmp_path)

    invalid_event = create_event(amount="-100")
    write_event(bronze_path, invalid_event)

    stats = pipeline.run()

    quarantine_file = quarantine_path / "rejected_events.jsonl"

    assert stats["transactions_quarantined"] == 1
    assert stats["transactions_written"] == 0
    assert quarantine_file.exists()

    rejected = json.loads(quarantine_file.read_text(encoding="utf-8").strip())

    assert rejected["original_event"]["event_id"] == (invalid_event["event_id"])
    assert rejected["rejection_reasons"]


def test_duplicate_event_is_skipped(tmp_path):
    pipeline, bronze_path, silver_path, _ = create_pipeline(tmp_path)

    event = create_event()

    write_event(bronze_path, event)
    write_event(bronze_path, event)

    stats = pipeline.run()

    records = SilverWriter(silver_path).read_all()

    assert stats["transactions_written"] == 1
    assert stats["duplicates_skipped"] == 1
    assert len(records) == 1


def test_empty_bronze_storage_returns_zero_counts(tmp_path):
    pipeline, _, _, _ = create_pipeline(tmp_path)

    stats = pipeline.run()

    assert stats == {
        "events_read": 0,
        "events_skipped_by_checkpoint": 0,
        "transactions_written": 0,
        "duplicates_skipped": 0,
        "transactions_quarantined": 0,
    }


def test_second_run_skips_checkpointed_events(tmp_path):
    pipeline, bronze_path, silver_path, _ = create_pipeline(tmp_path)

    write_event(bronze_path, create_event())

    first_run = pipeline.run()
    second_run = pipeline.run()

    records = SilverWriter(silver_path).read_all()

    assert first_run["transactions_written"] == 1
    assert second_run["events_read"] == 1
    assert second_run["events_skipped_by_checkpoint"] == 1
    assert second_run["transactions_written"] == 0
    assert len(records) == 1
