import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BronzeReader:
    """Read raw events from the Bronze JSONL storage layer."""

    def __init__(self, base_path: str | Path = "data/lake/bronze"):
        self.base_path = Path(base_path)

    def read_events(self) -> Iterator[dict[str, Any]]:
        """
        Read all valid JSON events from Bronze JSONL files.

        Malformed lines are logged and skipped.
        Original event dictionaries are returned unchanged.
        """
        if not self.base_path.exists():
            logger.warning("Bronze storage path does not exist: %s", self.base_path)
            return

        files = sorted(self.base_path.rglob("events.jsonl"))

        for file_path in files:
            logger.info("Reading Bronze file: %s", file_path)

            try:
                with file_path.open("r", encoding="utf-8") as file:
                    for line_number, line in enumerate(file, start=1):
                        if not line.strip():
                            continue

                        try:
                            event = json.loads(line)

                            if not isinstance(event, dict):
                                logger.warning(
                                    "Skipping non-object event at %s:%s",
                                    file_path,
                                    line_number,
                                )
                                continue

                            yield event

                        except json.JSONDecodeError:
                            logger.exception(
                                "Invalid JSON at %s:%s",
                                file_path,
                                line_number,
                            )

            except OSError:
                logger.exception("Could not read Bronze file: %s", file_path)
