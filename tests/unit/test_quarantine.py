import json

import pytest

from finpulse.processing.quarantine import QuarantineManager


@pytest.fixture
def original_event():
    return {
        "event_id": "event_001",
        "event_type": "TRANSACTION_CREATED",
        "payload": {
            "transaction_id": "txn_001",
            "amount": "-500",
            "source_type": "UPI_CSV",
        },
    }


def test_quarantine_record_is_saved(tmp_path, original_event):
    manager = QuarantineManager(tmp_path)

    manager.quarantine_record(
        original_event,
        ["amount: Input should be greater than 0"],
    )

    file_path = tmp_path / "rejected_events.jsonl"

    assert file_path.exists()

    with file_path.open(encoding="utf-8") as file:
        record = json.loads(file.readline())

    assert record["source_event_id"] == "event_001"
    assert record["original_event"] == original_event
    assert len(record["rejection_reasons"]) == 1


def test_multiple_rejected_records_are_saved(tmp_path, original_event):
    manager = QuarantineManager(tmp_path)

    manager.quarantine_record(original_event, ["Invalid amount"])

    second_event = {
        **original_event,
        "event_id": "event_002",
    }

    manager.quarantine_record(second_event, ["Missing user ID"])

    file_path = tmp_path / "rejected_events.jsonl"

    with file_path.open(encoding="utf-8") as file:
        records = [json.loads(line) for line in file]

    assert len(records) == 2


def test_original_event_is_preserved(tmp_path, original_event):
    manager = QuarantineManager(tmp_path)

    manager.quarantine_record(original_event, ["Invalid record"])

    assert original_event["payload"]["amount"] == "-500"


def test_empty_rejection_reasons_are_rejected(tmp_path, original_event):
    manager = QuarantineManager(tmp_path)

    with pytest.raises(
        ValueError,
        match="At least one rejection reason",
    ):
        manager.quarantine_record(original_event, [])


def test_rejection_timestamp_is_timezone_aware(tmp_path, original_event):
    manager = QuarantineManager(tmp_path)

    manager.quarantine_record(original_event, ["Invalid amount"])

    file_path = tmp_path / "rejected_events.jsonl"

    with file_path.open(encoding="utf-8") as file:
        record = json.loads(file.readline())

    from datetime import datetime

    timestamp = datetime.fromisoformat(record["rejected_at"])

    assert timestamp.tzinfo is not None
