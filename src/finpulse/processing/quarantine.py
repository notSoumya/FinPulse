import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class QuarantineManager:
    """Persist rejected transaction records as JSONL."""

    def __init__(
        self,
        base_path: str | Path = ("data/lake/quarantine/rejected_transactions"),
    ):
        self.base_path = Path(base_path)

    def quarantine_record(
        self,
        original_event: dict[str, Any],
        rejection_reasons: list[str],
    ) -> None:
        """Store an invalid event with its rejection reasons."""

        if not rejection_reasons:
            raise ValueError("At least one rejection reason is required")

        record = {
            "source_event_id": original_event.get("event_id"),
            "rejected_at": datetime.now(UTC).isoformat(),
            "rejection_reasons": rejection_reasons,
            "original_event": original_event,
        }

        self.base_path.mkdir(parents=True, exist_ok=True)

        file_path = self.base_path / "rejected_events.jsonl"

        with file_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
            file.flush()
