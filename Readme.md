## Bronze Storage Layer

FinPulse implements a Bronze layer to persist raw financial transaction events received through Apache Kafka.

### Architecture

```text
FastAPI Ingestion API
        |
        v
Kafka Producer
        |
        v
Apache Kafka Topics
        |
        v
Kafka Consumer / Worker
        |
        v
Event Validation
        |
        v
Bronze Storage (JSONL)
```

### Key Features

- **Raw Event Preservation:** Stores original Kafka event envelopes without modifying transaction payloads.
- **Partitioning:** Organizes events by source type, year, month, and day using UTC timestamps.
- **Idempotency:** Prevents duplicate event IDs from being stored.
- **Failure Handling:** Retries failed operations and sends invalid events to Dead Letter Queue (DLQ) topics.
- **Safe Offset Management:** Commits Kafka offsets only after successful Bronze persistence or successful DLQ publishing.

### Storage Structure

```text
data/
└── lake/
    └── bronze/
        └── source_type=MANUAL/
            └── year=2026/
                └── month=11/
                    └── day=09/
                        └── events.jsonl
```

### Running the Kafka Infrastructure

Start Kafka:

```powershell
docker compose -f docker-compose.kafka.yml up -d
```

Initialize Kafka topics:

```powershell
python scripts/create_topics.py
```

Start the Kafka worker:

```powershell
python scripts/run_worker.py
```

Start the FastAPI application in another terminal:

```powershell
uvicorn finpulse.ingestion.main:app --reload
```

### Running Tests

Run the complete test suite:

```powershell
python -m pytest -v
```

Check code quality:

```powershell
ruff check .
```

**Note:** Bronze storage currently uses local JSONL files for zero-cost development. Cloud object storage can be introduced later.