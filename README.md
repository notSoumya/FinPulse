# FinPulse ⚡

> **Personal Finance Intelligence Platform**  
> A real-time data engineering and intelligence pipeline for multi-source financial transaction ingestion, bronze storage, and analytics.

---

## 📌 Overview

**FinPulse** is a modern financial data platform engineered to ingest, validate, store, and analyze transactional data from diverse unstructured and semi-structured sources:
- **Bank SMS Notifications**
- **UPI Statements (CSV)**
- **Credit Card Statements (PDF)**
- **Manual User Submissions**

It establishes a shared canonical data contract across services, streams events via **Apache Kafka** with retry and Dead-Letter Queue (DLQ) safeguards, and archives events into an immutable **Bronze Data Lake** partition structure before downstream transformation and warehouse ingestion.

---

## 🏗️ Architecture

```
[ Financial Sources ]
  ├── Bank SMS
  ├── UPI CSV        ──► [ Ingestion Service (FastAPI) ]
  ├── Card PDF                │ (Validation & Canonical Schema)
  └── Manual Entry            ▼
                      [ Apache Kafka Streaming ]
                       ├── finpulse.transactions (Main Event Stream)
                       └── finpulse.transactions.dlq (Dead-Letter Queue)
                              │
                              ▼
                      [ Ingestion Worker ]
                              │
                              ▼
                      [ Bronze Storage ]
                       (Partitioned JSONL: data/lake/bronze/year=YYYY/month=MM/day=DD/)
                              │
                              ▼
                      [ Downstream / Warehouse ]
                       (dbt & BigQuery Transformations)
```

---

## 🚀 Key Features

- **Canonical Data Contract**: Strict Pydantic-based transaction schema ensuring consistent timestamps (UTC), currency formatting, and deterministic transaction/payload hashing.
- **Resilient Kafka Ingestion**: Reliable event streaming with exponential backoff retries and automatic routing of malformed or unprocessable payloads to DLQ.
- **Bronze Storage Engine**: Partitioned (`year=YYYY/month=MM/day=DD`), immutable raw event storage with built-in deduplication and audit tracking.
- **Modular Ingestion Parsers**: Dedicated parsers for UPI CSVs, regex-based bank SMS alerts, PDF statements, and manual payloads.
- **End-to-End Test Suite**: Comprehensive unit tests covering schemas, hashing, parsers, DLQ handling, and storage partitions.

---

## 📁 Repository Structure

```text
FinPulse/
├── airflow/                    # Orchestration DAGs
├── benchmarks/                 # Pipeline benchmarks & performance results
├── config/                     # Configuration files and templates
├── dashboard/                  # Streamlit analytics dashboards
├── data/
│   ├── lake/bronze/            # Partitioned Bronze data lake
│   └── raw_samples/            # Sample input files
├── dbt/                        # dbt models for BigQuery transformation
├── docs/                       # Architecture docs and data contracts
├── scripts/
│   ├── create_topics.py        # Kafka topic initialization
│   └── run_worker.py           # Consumer & Bronze storage worker
├── src/finpulse/
│   ├── bronze/                 # Bronze storage writer & partitioning
│   ├── common/                 # Models, hashing utilities, constants
│   ├── ingestion/              # Ingestion API & source parsers
│   └── messaging/              # Kafka producer, consumer, retry, & DLQ
├── tests/
│   ├── fixtures/               # Test fixtures and mock files
│   ├── integration/            # Ingestion API integration tests
│   └── unit/                   # Unit test suite
├── docker-compose.kafka.yml    # Kafka & Zookeeper infrastructure
└── pyproject.toml              # Project dependencies and configuration
```

---

## ⚙️ Getting Started

### 1. Prerequisites
- **Python 3.11+**
- **Docker & Docker Compose** (for Kafka & Zookeeper)

### 2. Environment Setup

Clone the repository and navigate into the project directory:

```bash
git clone https://github.com/notSoumya/FinPulse.git
cd FinPulse
```

Create and activate a virtual environment:

```bash
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

Install dependencies in editable mode:

```bash
pip install -e ".[dev,ingestion,messaging,lake]"
```

Configure environment variables:

```bash
cp .env.example .env
```

---

## 🛠️ Running the Platform

### Step 1: Start Kafka & Zookeeper
```bash
docker compose -f docker-compose.kafka.yml up -d
```

### Step 2: Initialize Kafka Topics
```bash
python scripts/create_topics.py
```

### Step 3: Run the Ingestion API
```bash
uvicorn finpulse.ingestion.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### Step 4: Run the Messaging Worker
In a separate terminal, launch the worker to consume incoming events and persist them into Bronze storage:
```bash
python scripts/run_worker.py
```

---

## 🧪 Testing

Run the test suite with `pytest`:

```bash
pytest
```

To run unit tests specifically:
```bash
pytest tests/unit/
```

To run tests with code coverage:
```bash
pytest --cov=finpulse
```

---

## 📜 Shared Data Contract

Transactions adhere to the canonical schema defined in [`docs/data_contract.md`](docs/data_contract.md):

| Field | Type | Description |
|---|---|---|
| `transaction_id` | String | Deterministic unique transaction identifier |
| `user_id` | String | User identifier |
| `amount` | Decimal | Positive transaction amount |
| `currency` | String | Normalized 3-letter currency code (e.g. `INR`) |
| `direction` | Enum | `DEBIT` or `CREDIT` |
| `transaction_timestamp` | Datetime | Timezone-aware UTC timestamp |
| `source_type` | Enum | `BANK_SMS`, `UPI_CSV`, `CARD_PDF`, or `MANUAL` |
| `merchant_raw` | String? | Original merchant string |
| `merchant_normalized` | String? | Standardized merchant name |
| `reference_id` | String? | Bank/UPI reference ID |

---

## 📄 License

This project is licensed under the terms specified in the repository.
