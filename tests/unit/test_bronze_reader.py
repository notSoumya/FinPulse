import json

from finpulse.processing.bronze_reader import BronzeReader


def test_reads_valid_events(tmp_path):
    bronze_path = tmp_path / "bronze"
    bronze_path.mkdir()

    event = {
        "event_id": "event_001",
        "event_type": "TRANSACTION_CREATED",
        "payload": {"transaction_id": "txn_001"},
    }

    event_file = bronze_path / "events.jsonl"
    event_file.write_text(json.dumps(event) + "\n", encoding="utf-8")

    reader = BronzeReader(bronze_path)

    events = list(reader.read_events())

    assert len(events) == 1
    assert events[0] == event


def test_reads_multiple_events(tmp_path):
    bronze_path = tmp_path / "bronze"
    bronze_path.mkdir()

    events_to_write = [
        {"event_id": "event_001"},
        {"event_id": "event_002"},
    ]

    event_file = bronze_path / "events.jsonl"

    with event_file.open("w", encoding="utf-8") as file:
        for event in events_to_write:
            file.write(json.dumps(event) + "\n")

    reader = BronzeReader(bronze_path)

    events = list(reader.read_events())

    assert len(events) == 2


def test_skips_malformed_json(tmp_path):
    bronze_path = tmp_path / "bronze"
    bronze_path.mkdir()

    event_file = bronze_path / "events.jsonl"
    event_file.write_text(
        '{"event_id": "event_001"}\nthis is invalid json\n{"event_id": "event_002"}\n',
        encoding="utf-8",
    )

    reader = BronzeReader(bronze_path)

    events = list(reader.read_events())

    assert len(events) == 2


def test_returns_empty_when_path_does_not_exist(tmp_path):
    reader = BronzeReader(tmp_path / "missing")

    events = list(reader.read_events())

    assert events == []


def test_skips_empty_lines(tmp_path):
    bronze_path = tmp_path / "bronze"
    bronze_path.mkdir()

    event_file = bronze_path / "events.jsonl"
    event_file.write_text(
        '{"event_id": "event_001"}\n\n{"event_id": "event_002"}\n',
        encoding="utf-8",
    )

    reader = BronzeReader(bronze_path)

    events = list(reader.read_events())

    assert len(events) == 2
