import json

import pytest

from finpulse.processing.checkpoint import CheckpointManager


def test_new_checkpoint_starts_empty(tmp_path):
    manager = CheckpointManager(tmp_path / "checkpoint.json")

    assert manager.processed_event_ids == set()


def test_mark_event_as_processed(tmp_path):
    path = tmp_path / "checkpoint.json"
    manager = CheckpointManager(path)

    manager.mark_processed("event_001")

    assert manager.is_processed("event_001")


def test_checkpoint_persists_after_reload(tmp_path):
    path = tmp_path / "checkpoint.json"

    manager = CheckpointManager(path)
    manager.mark_processed("event_001")

    reloaded = CheckpointManager(path)

    assert reloaded.is_processed("event_001")


def test_multiple_events_are_persisted(tmp_path):
    path = tmp_path / "checkpoint.json"
    manager = CheckpointManager(path)

    manager.mark_processed("event_001")
    manager.mark_processed("event_002")

    reloaded = CheckpointManager(path)

    assert reloaded.processed_event_ids == {
        "event_001",
        "event_002",
    }


def test_empty_event_id_is_rejected(tmp_path):
    manager = CheckpointManager(tmp_path / "checkpoint.json")

    with pytest.raises(ValueError):
        manager.mark_processed("")


def test_invalid_checkpoint_format_is_rejected(tmp_path):
    path = tmp_path / "checkpoint.json"

    path.write_text(
        json.dumps({"processed_event_ids": "not-a-list"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        CheckpointManager(path)
