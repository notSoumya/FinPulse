from finpulse.common.models import Transaction


def process_event(event: dict) -> Transaction:
    """Validate a Kafka transaction event and return its transaction."""

    required_fields = {
        "event_id",
        "event_timestamp",
        "schema_version",
        "event_type",
        "payload",
    }

    missing_fields = required_fields - event.keys()

    if missing_fields:
        raise ValueError(f"Kafka event is missing fields: {sorted(missing_fields)}")

    if event["event_type"] != "TRANSACTION_CREATED":
        raise ValueError(f"Unsupported event type: {event['event_type']}")

    if not isinstance(event["payload"], dict):
        raise ValueError("Event payload must be a dictionary")

    return Transaction.model_validate(event["payload"])
