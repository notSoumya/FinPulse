
import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from finpulse.common.constants import SOURCE_TYPES

logger = logging.getLogger(__name__)


class BronzeStorage:
    def __init__(self, base_path: str | Path = "data/lake/bronze"):
        self.base_path = Path(base_path)
        self._lock = threading.Lock()

    def _get_partition_path(self, event: dict[str, Any]) -> Path:
        event_id = event.get("event_id")
        event_timestamp = event.get("event_timestamp")
        payload = event.get("payload")

        if not event_id:
            raise ValueError("Event must contain event_id")

        if not isinstance(payload, dict):
            raise ValueError("Event payload must be a dictionary")

        source_type = payload.get("source_type")

        if source_type not in SOURCE_TYPES:
            raise ValueError(f"Unsupported source type: {source_type}")

        if not event_timestamp:
            raise ValueError("Event must contain event_timestamp")

        try:
            timestamp = datetime.fromisoformat(
                event_timestamp.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError) as exc:
            raise ValueError("Invalid event_timestamp") from exc

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("event_timestamp must include timezone information")

        timestamp = timestamp.astimezone(UTC)

        return (
            self.base_path
            / f"source_type={source_type}"
            / f"year={timestamp.year}"
            / f"month={timestamp.month:02d}"
            / f"day={timestamp.day:02d}"
            / "events.jsonl"
        )

    def _event_exists(self, file_path: Path, event_id: str) -> bool:
        if not file_path.exists():
            return False

        with file_path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue

                stored_event = json.loads(line)

                if stored_event.get("event_id") == event_id:
                    return True

        return False

    def write_event(self, event: dict[str, Any]) -> bool:
        """
        Write an event to Bronze storage.

        Returns True if written, False if already present.
        """
        file_path = self._get_partition_path(event)
        event_id = event["event_id"]

        serialized_event = json.dumps(
            event,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        with self._lock:
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if self._event_exists(file_path, event_id):
                logger.info("Duplicate event skipped: %s", event_id)
                return False

            with file_path.open("a", encoding="utf-8") as file:
                file.write(serialized_event + "\n")
                file.flush()

            logger.info("Bronze event stored: %s", event_id)

        return True
