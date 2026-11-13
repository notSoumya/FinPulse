# FinPulse ⚡

> **Personal Finance Intelligence Platform**  
> An end-to-end data engineering and intelligence platform for multi-source financial transaction ingestion, bronze storage, ACID silver curation, analytical warehouse modeling, and financial intelligence.

---

## 📌 Overview

**FinPulse** is a modern financial data platform engineered to ingest, validate, store, transform, and analyze transactional data from diverse unstructured and semi-structured sources:
- **Bank SMS Notifications**
- **UPI Statements (CSV)**
- **Credit Card Statements (PDF)**
- **Manual User Submissions**

It establishes a shared canonical data contract across services, streams events via **Apache Kafka** with retry and Dead-Letter Queue (DLQ) safeguards, archives raw events into an immutable **Bronze Data Lake** partition structure, curates records into an ACID **Silver Delta Lake** table, and aggregates business metrics in an embedded, zero-cost **DuckDB Analytical Warehouse** powered by **dbt-duckdb**.

---

## 🗺️ Project Roadmap & Phase Status

| Phase | Milestone | Scope / Deliverables | Status |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Project Setup & Standards | Repository structure, dependencies, `.gitignore`, Ruff, Pytest | **Completed** |
| **Phase 2** | Shared Data Contract | Canonical Pydantic schema, deterministic SHA-256 hashing, constants | **Completed** |
| **Phase 3** | Ingestion Engine | FastAPI ingestion endpoints, parsers (SMS, UPI CSV, PDF, Manual) | **Completed** |
| **Phase 4** | Messaging Layer | Kafka producer, consumer, topic configuration, retry mechanism, DLQ | **Completed** |
| **Phase 5** | Bronze Data Lake | Immutable JSONL partitioned storage (`year/month/day`), offset commits | **Completed** |
| **Phase 6** | Silver Processing Layer | Bronze reader, validation, cleaner, deduplicator, Delta Lake writer | **Completed** |
| **Phase 7** | Warehouse Architecture & Modeling | DuckDB warehouse, dbt-duckdb transformations, Gold Marts, pipeline runner | **Completed** |
| **Phase 8** | Workflow Orchestration | Apache Airflow DAGs for automated batch pipeline scheduling, retries, quality validation | **Completed** |
| **Phase 9** | Intelligence & Visualizations | ML anomaly detection and Streamlit personal finance dashboard | **Next Planned Phase** |

---

## 🏗️ Architecture

```text
[ Ingestion Sources ]
  ├── Bank SMS
  ├── UPI CSV        ──► [ Ingestion Service (FastAPI) ]
  ├── Card PDF                │ (Validation & Canonical Schema)
  └── Manual Entry            ▼
                      [ Apache Kafka Streaming ]
                       ├── finpulse.transactions (Main Event Stream)
                       └── finpulse.transactions.dlq (Dead-Letter Queue)
                              │
                              ▼
                      [ Kafka Ingestion Worker ]
                              │
                              ▼
                      [ Bronze Data Lake ]
                       (Partitioned JSONL: data/lake/bronze/source_type=.../year=.../)
                              │
                              ▼
                      [ Silver Processing Pipeline ]
                       (Validation, Cleaning, Deduplication, Checkpointing)
                              │
                              ▼
                      [ Silver Delta Lake ]
                       (ACID Parquet Storage: data/lake/silver/transactions)
                              │
                              ▼
                      [ Warehouse Sync & Transformation ]
                       (DuckDB Loader & dbt-duckdb Runner)
                              │
                              ▼
                      [ DuckDB Analytical Warehouse ]
                       (data/warehouse/finpulse.duckdb)
                       ├── Staging: stg_transactions (View)
                       ├── Intermediate: int_daily_transactions (View)
                       └── Gold Marts (Tables):
                           ├── gold_daily_spending
                           ├── gold_monthly_spending
                           ├── gold_merchant_spending
                           ├── gold_cashflow_summary
                           └── gold_category_spending
```

---

## 🏛️ Phase 7 — Analytical Warehouse & dbt Modeling

Phase 7 establishes a high-performance, embedded, zero-cost analytical data warehouse upstreamed directly from the Silver Delta Lake.

### Delivered Technologies
- **Delta Lake**: ACID storage engine and commit log reader.
- **PyArrow**: Columnar in-memory data structures preserving exact Decimal amounts.
- **DuckDB**: Embedded analytical columnar SQL OLAP database.
- **dbt-duckdb**: SQL transformation DAG, data testing, and documentation framework.
- **Python dbtRunner**: Programmatic orchestration of dbt execution within pipeline scripts.
- **Pytest**: Automated unit and end-to-end integration testing.
- **Ruff**: Fast Python linter enforcing PEP 8 and clean architecture standards.

### Verified Results
- **132 unit and integration tests passed** (0 failures, 0 errors).
- **27 dbt data tests passed** (unique keys, not-null constraints, accepted values, positive amounts).
- **7 dbt models passed** (1 staging view, 1 intermediate view, 5 gold analytical tables).
- **34 total dbt model/test executions passed**.
- **Ruff code quality: 0 errors**.

### Gold Analytical Marts
1. `gold_daily_spending`: Daily debits, credits, net cash flow, and transaction volumes.
2. `gold_monthly_spending`: Monthly expenses, income, net savings, and savings rate percentage.
3. `gold_merchant_spending`: Outflows by merchant, frequency, and average ticket size.
4. `gold_cashflow_summary`: Aggregated inflow vs. outflow ratio and total volume share.
5. `gold_category_spending`: Spending categorized across essential and discretionary categories.

---

## 📁 Repository Structure

```text
FinPulse/
├── airflow/                    # Phase 8: Orchestration DAGs
├── config/                     # Configuration files and merchant mappings
├── data/
│   ├── lake/
│   │   ├── bronze/             # Partitioned Bronze JSONL files
│   │   └── silver/             # Silver Delta Lake tables
│   └── warehouse/              # DuckDB database file (finpulse.duckdb)
├── dbt/
│   ├── dbt_project.yml         # dbt project configuration
│   ├── profiles.yml            # DuckDB local adapter profile
│   └── models/
│       ├── staging/            # Staging views & schema tests
│       ├── intermediate/       # Daily rollup intermediate views
│       └── marts/              # Gold analytical tables & schema tests
├── docs/                       # Architecture specifications & implementation logs
├── scripts/
│   ├── create_topics.py        # Kafka topic initialization
│   ├── run_worker.py           # Consumer & Bronze storage worker
│   ├── run_silver_pipeline.py  # Bronze-to-Silver ETL pipeline runner
│   └── run_warehouse.py        # Silver-to-DuckDB & dbt pipeline runner
├── src/finpulse/
│   ├── bronze/                 # Bronze storage writer & partitioning
│   ├── common/                 # Models, hashing utilities, constants
│   ├── ingestion/              # Ingestion API & source parsers
│   ├── messaging/              # Kafka producer, consumer, retry, & DLQ
│   ├── processing/             # Silver reader, cleaner, validator, deduplicator
│   ├── silver/                 # Silver models, PyArrow schema, Delta writer
│   └── warehouse/              # DuckDB loader and pipeline orchestrator
├── tests/
│   ├── integration/            # API and warehouse end-to-end integration tests
│   └── unit/                   # Unit test suite across all modules
├── docker-compose.kafka.yml    # Kafka & Zookeeper infrastructure
└── pyproject.toml              # Dependencies and packaging configuration
```

---

## ⚙️ Getting Started

### 1. Prerequisites
- **Python 3.11+**
- **Docker & Docker Compose** (for Kafka & Zookeeper)

### 2. Environment Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/notSoumya/FinPulse.git
cd FinPulse

# Install dependencies in editable mode
pip install -e ".[dev,ingestion,messaging,lake,warehouse]"
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

### Step 3: Run Ingestion Worker
```bash
python scripts/run_worker.py
```

### Step 4: Run Bronze-to-Silver Processing Pipeline
```bash
python scripts/run_silver_pipeline.py
```

### Step 5: Run Warehouse Ingestion & dbt Transformations
Sync Silver transactions into DuckDB and execute dbt data models and tests:
```bash
python scripts/run_warehouse.py
```

### Step 6: Orchestrate with Apache Airflow
Run the complete automated pipeline using Apache Airflow:
```bash
# Start Airflow metadata database and webserver/scheduler
docker compose -f docker-compose.airflow.yml up airflow-init
docker compose -f docker-compose.airflow.yml up -d
```
Access the Airflow UI at `http://localhost:8080` (credentials: `admin` / `admin`) to trigger or monitor `finpulse_end_to_end_pipeline`.

---

## 🧪 Testing & Verification

Run the full automated test suite (148 tests across unit, integration, and DAG verification):
```bash
pytest -v
```

Run code formatting and lint verification:
```bash
ruff check .
```

---

## 📜 Shared Data Contract

Transactions adhere to the canonical schema defined in [`docs/data_contract.md`](docs/data_contract.md):

| Field | Type | Description |
|---|---|---|
| `transaction_id` | String | Deterministic unique transaction identifier |
| `user_id` | String | User identifier |
| `amount` | Decimal(18, 2) | Positive transaction amount (exact precision) |
| `currency` | String | Normalized 3-letter currency code (e.g. `INR`) |
| `direction` | Enum | `DEBIT` or `CREDIT` |
| `transaction_timestamp` | Datetime (UTC) | Timezone-aware UTC timestamp |
| `source_type` | Enum | `BANK_SMS`, `UPI_CSV`, `CARD_PDF`, or `MANUAL` |
| `merchant_raw` | String? | Original merchant string |
| `merchant_normalized` | String? | Standardized merchant name |
| `reference_id` | String? | Bank/UPI reference ID |
| `deduplication_key` | String | Hash fingerprint for deduplication |
| `processed_at` | Datetime (UTC) | Silver processing timestamp |

---

## 📄 License

This project is licensed under the terms specified in the repository.
