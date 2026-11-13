import json
from pathlib import Path


class CheckpointManager:
    """Track Bronze events successfully processed by Silver."""

    def __init__(
        self,
        checkpoint_path: str | Path = ("data/lake/checkpoints/silver_checkpoint.json"),
    ):
        self.checkpoint_path = Path(checkpoint_path)
        self.processed_event_ids: set[str] = set()
        self.load()

    def load(self) -> None:
        """Load previously processed event IDs."""

        if not self.checkpoint_path.exists():
            self.processed_event_ids = set()
            return

        with self.checkpoint_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        event_ids = data.get("processed_event_ids", [])

        if not isinstance(event_ids, list) or not all(
            isinstance(event_id, str) and event_id for event_id in event_ids
        ):
            raise ValueError("Invalid checkpoint event IDs")

        self.processed_event_ids = set(event_ids)

    def is_processed(self, event_id: str) -> bool:
        """Check whether an event has already been processed."""

        return event_id in self.processed_event_ids

    def mark_processed(self, event_id: str) -> None:
        """Persist an event ID after successful processing."""

        if not event_id:
            raise ValueError("event_id cannot be empty")

        self.processed_event_ids.add(event_id)

        self.checkpoint_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self.checkpoint_path.with_suffix(".tmp")

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                {"processed_event_ids": sorted(self.processed_event_ids)},
                file,
                indent=4,
            )
            file.flush()

        temporary_path.replace(self.checkpoint_path)
