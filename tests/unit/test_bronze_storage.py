import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from finpulse.bronze.storage import BronzeStorage


@pytest.fixture
def valid_event():
    return {
        "event_id": "event_001",
        "event_timestamp": datetime(2026, 11, 9, 10, 30, tzinfo=UTC).isoformat(),
        "schema_version": "1.0",
        "event_type": "TRANSACTION_CREATED",
        "payload": {
            "transaction_id": "txn_001",
            "user_id": "user_001",
            "amount": "500.00",
            "currency": "INR",
            "direction": "DEBIT",
            "source_type": "MANUAL",
        },
    }


def test_write_event_creates_jsonl_file(tmp_path, valid_event):
    storage = BronzeStorage(tmp_path)

    result = storage.write_event(valid_event)

    assert result is True

    files = list(Path(tmp_path).rglob("events.jsonl"))
    assert len(files) == 1

    with files[0].open(encoding="utf-8") as file:
        stored_event = json.loads(file.readline())

    assert stored_event == valid_event


def test_duplicate_event_is_not_written(tmp_path, valid_event):
    storage = BronzeStorage(tmp_path)

    assert storage.write_event(valid_event) is True
    assert storage.write_event(valid_event) is False

    files = list(Path(tmp_path).rglob("events.jsonl"))

    with files[0].open(encoding="utf-8") as file:
        lines = file.readlines()

    assert len(lines) == 1


def test_event_is_stored_in_correct_partition(tmp_path, valid_event):
    storage = BronzeStorage(tmp_path)

    storage.write_event(valid_event)

    expected = (
        Path(tmp_path) / "source_type=MANUAL" / "year=2026" / "month=11" / "day=09" / "events.jsonl"
    )

    assert expected.exists()


def test_missing_event_id_is_rejected(tmp_path, valid_event):
    storage = BronzeStorage(tmp_path)
    del valid_event["event_id"]

    with pytest.raises(ValueError, match="event_id"):
        storage.write_event(valid_event)


def test_invalid_source_type_is_rejected(tmp_path, valid_event):
    storage = BronzeStorage(tmp_path)
    valid_event["payload"]["source_type"] = "UNKNOWN"

    with pytest.raises(ValueError, match="Unsupported source type"):
        storage.write_event(valid_event)


def test_timezone_is_required(tmp_path, valid_event):
    storage = BronzeStorage(tmp_path)
    valid_event["event_timestamp"] = "2026-11-09T10:30:00"

    with pytest.raises(ValueError, match="timezone"):
        storage.write_event(valid_event)


def test_event_is_partitioned_using_utc(tmp_path, valid_event):
    storage = BronzeStorage(tmp_path)

    # 2026-11-10 01:00 IST = 2026-11-09 19:30 UTC
    valid_event["event_timestamp"] = "2026-11-10T01:00:00+05:30"

    storage.write_event(valid_event)

    expected = (
        Path(tmp_path) / "source_type=MANUAL" / "year=2026" / "month=11" / "day=09" / "events.jsonl"
    )

    assert expected.exists()


def test_invalid_timestamp_is_rejected(tmp_path, valid_event):
    storage = BronzeStorage(tmp_path)
    valid_event["event_timestamp"] = "not-a-valid-timestamp"

    with pytest.raises(ValueError, match="Invalid event_timestamp"):
        storage.write_event(valid_event)


def test_missing_payload_is_rejected(tmp_path, valid_event):
    storage = BronzeStorage(tmp_path)
    valid_event["payload"] = None

    with pytest.raises(ValueError, match="payload"):
        storage.write_event(valid_event)
