# FinPulse — Phase 8: Workflow Orchestration Architecture

**Document Status:** Stage 1 Architecture Inspection & Proposed Design  
**Author:** Antigravity Data Platform Agent  
**Date:** 2026-11-13  
**Target Milestone:** Phase 8 — End-to-End Workflow Orchestration Using Apache Airflow  
**Upstream Modules:** Phases 1–7 (Bronze Lake, Silver Delta Lake, DuckDB Warehouse, dbt-duckdb)  

---

## 1. Executive Summary & Objective

In Phases 1–7, FinPulse established an end-to-end data platform covering multi-source ingestion, Kafka messaging, Bronze JSONL storage, Silver Delta Lake cleaning/deduplication, and a local DuckDB analytical warehouse modeled with dbt-duckdb.

However, execution across these layers currently requires manual invocation of individual scripts (`run_worker.py`, `run_silver_pipeline.py`, `run_warehouse.py`). 

The objective of **Phase 8** is to transform FinPulse into an enterprise-grade automated system orchestrated by **Apache Airflow**. Airflow will manage:
- Directed Acyclic Graph (DAG) task scheduling and dependencies.
- Automated upstream-to-downstream failure propagation.
- Retry policies with exponential backoff.
- Centralized execution logging and task state auditing.
- Isolation of pipeline stages while reusing 100% of existing, verified business logic.

---

## 2. Existing Architecture Inspection & Reusability Audit

A comprehensive code inspection of the FinPulse repository reveals the following components and callable interfaces:

### A. Bronze Ingestion Layer
- **Source Parsers:** [`src/finpulse/ingestion/parsers/`](file:///d:/FinpulseDE/FinPulse/src/finpulse/ingestion/parsers/) contains parsers for UPI CSV (`parse_upi_csv`), Card PDF (`parse_card_pdf`), Bank SMS (`parse_bank_sms`), and Manual entries (`parse_manual`).
- **Kafka Worker:** [`src/finpulse/messaging/worker.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/messaging/worker.py) consumes from Kafka topic `finpulse.transactions`, executes validation with retries, and writes to Bronze storage.
- **Bronze Storage Writer:** [`src/finpulse/bronze/storage.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/bronze/storage.py) (`BronzeStorage.write_event(event)`) writes raw envelopes to partitioned JSONL files under `data/lake/bronze/source_type={type}/year={YYYY}/month={MM}/day={DD}/events.jsonl`.
- **Airflow Integration Callable:** A dedicated batch ingestion helper `ingest_bronze_batch()` will coordinate reading pending raw input files from drop directories (e.g. `data/raw_samples/` or staged inputs) or draining the Kafka queue into `BronzeStorage`, validating event envelope structure without duplicating storage logic.

### B. Silver Processing & Transformation Layer
- **Pipeline Class:** [`src/finpulse/processing/silver_pipeline.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/processing/silver_pipeline.py) exposes `SilverPipeline().run() -> dict[str, int]`.
- **Functionality:**
  1. Reads Bronze JSONL files incrementally via `BronzeReader`.
  2. Filters already processed events using `CheckpointManager` (`data/lake/silver/_checkpoints/processed_events.json`).
  3. Validates event schemas (`validator.py`) and routes malformed records to `QuarantineManager` (`data/lake/quarantine/`).
  4. Standardizes amounts (`Decimal(18, 2)`), UTC timestamps, and currencies (`cleaner.py`).
  5. Standardizes merchants via `MerchantNormalizer` (`config/merchant_mapping.json`).
  6. Deduplicates against existing Delta records via `is_duplicate()`.
  7. Writes clean records to Delta Lake table at `data/lake/silver/transactions` via `SilverWriter`.
- **Airflow Integration Callable:** Directly call `SilverPipeline().run()` in a PythonOperator. The function returns a execution dictionary (`events_read`, `transactions_written`, `duplicates_skipped`, `transactions_quarantined`) which will be pushed to Airflow XCom for downstream auditing.

### C. Warehouse Synchronization Layer
- **Loader Class:** [`src/finpulse/warehouse/loader.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/warehouse/loader.py) exposes `WarehouseLoader(silver_path, db_path).sync() -> int`.
- **Functionality:**
  - Reads the Silver Delta Lake table via PyArrow (`DeltaTable.to_pyarrow_table()`).
  - Idempotently overwrites table `silver.transactions` in `data/warehouse/finpulse.duckdb`.
  - Preserves exact `DECIMAL(18, 2)` monetary values and `TIMESTAMPTZ` UTC datetimes.
  - Handles missing or empty Delta tables gracefully.
- **Airflow Integration Callable:** Directly call `sync_silver_to_duckdb()` or `WarehouseLoader().sync()`.

### D. dbt Transformation & Data Quality Layers
- **dbt Project:** [`dbt/dbt_project.yml`](file:///d:/FinpulseDE/FinPulse/dbt/dbt_project.yml) and [`dbt/profiles.yml`](file:///d:/FinpulseDE/FinPulse/dbt/profiles.yml).
- **Transformation Engine:** `dbtRunner().invoke(["run", ...])` builds 7 models (1 staging view, 1 intermediate view, 5 gold analytical marts).
- **Data Quality Engine:** `dbtRunner().invoke(["test", ...])` executes 27 generic and business logic data tests.
- **Airflow Integration Callables:** Separate tasks:
  1. `run_dbt_transformations()` invoking `dbtRunner().invoke(["run", ...])`.
  2. `run_dbt_data_tests()` invoking `dbtRunner().invoke(["test", ...])`.

---

## 3. Proposed Airflow Architecture

```
                  ┌─────────────────────────────────────────────────────────┐
                  │          Apache Airflow (Scheduler & Webserver)         │
                  └────────────────────────────┬────────────────────────────┘
                                               │
               DAG: finpulse_end_to_end_pipeline (Schedule: @daily / Manual)
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │          Task 1: bronze_ingestion         │
                         │ (Ingest/validate raw files to Bronze JSONL)│
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │       Task 2: silver_transformation       │
                         │ (Clean, normalize, dedup -> Delta Lake)   │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │        Task 3: warehouse_sync             │
                         │ (Delta Lake -> PyArrow -> DuckDB silver)  │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │       Task 4: dbt_transformations         │
                         │ (dbt run: stg -> int -> 5 gold marts)     │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │      Task 5: data_quality_validation      │
                         │ (dbt test: 27 schema & business checks)   │
                         └───────────────────────────────────────────┘
```

---

## 4. DAG Task Responsibilities & Data Contract

| Task ID | Operator / Callable | Inputs | Outputs | Failure Condition |
| :--- | :--- | :--- | :--- | :--- |
| **`bronze_ingestion`** | `PythonOperator` (`ingest_bronze_task`) | Raw input files (`data/raw_samples/` or Kafka) | Partitioned Bronze JSONL (`data/lake/bronze/`) | Unreadable files, filesystem permissions, envelope schema violation. |
| **`silver_transformation`** | `PythonOperator` (`silver_pipeline_task`) | `data/lake/bronze/` JSONL partitions | `data/lake/silver/transactions` (Delta Lake) & checkpoint JSON | Unhandled corrupt data, Delta log lock failure, write failure. |
| **`warehouse_sync`** | `PythonOperator` (`warehouse_sync_task`) | `data/lake/silver/transactions` | `data/warehouse/finpulse.duckdb` (`silver.transactions`) | Database write lock, PyArrow schema mismatch. |
| **`dbt_transformations`** | `PythonOperator` (`dbt_run_task`) | `silver.transactions` in DuckDB | Staging views, intermediate views, Gold tables | SQL syntax error, model compile failure, broken column reference. |
| **`data_quality_validation`**| `PythonOperator` (`dbt_test_task`) | DuckDB models (`stg`, `int`, `gold`) | Test report (27 tests) | Any `FAIL` in uniqueness, not-null, accepted values, or positive amounts. |

---

## 5. Configuration & Environment Management

All parameters will be configurable with clean fallbacks:
- `FINPULSE_HOME`: Root repository directory (defaults to current working directory).
- `FINPULSE_SILVER_PATH`: Delta table path (default: `data/lake/silver/transactions`).
- `FINPULSE_DUCKDB_PATH`: DuckDB database path (default: `data/warehouse/finpulse.duckdb`).
- `FINPULSE_DBT_PROJECT_DIR`: dbt directory (default: `dbt`).
- `FINPULSE_DBT_PROFILES_DIR`: dbt profiles directory (default: `dbt`).
- Airflow variables and connections will be leveraged for schedule intervals, alert emails, and retry caps without hardcoding machine-specific paths.

---

## 6. Error Handling & Reliability Strategy

1. **Strict Upstream Failure Propagation:**
   - Downstream tasks will strictly use `TriggerRule.ALL_SUCCESS`.
   - If `silver_transformation` fails, `warehouse_sync` **will not run**.
   - If `warehouse_sync` fails, `dbt_transformations` **will not run**.
   - If `dbt_transformations` fails, `data_quality_validation` **will not run**.
2. **Deterministic Retries & Idempotency:**
   - **Silver Retries:** Because `SilverWriter` uses deduplication keys and `CheckpointManager` records processed event IDs, re-running the Silver task never duplicates transactions in Delta Lake.
   - **Warehouse Sync Retries:** `WarehouseLoader` performs an ACID table replacement in DuckDB; repeating it produces an identical, consistent state.
   - **dbt Retries:** Views are replaced (`CREATE OR REPLACE VIEW`) and Mart tables are recreated (`CREATE OR REPLACE TABLE`); completely idempotent.
3. **Retry Configuration:**
   - `retries: 2`
   - `retry_delay: timedelta(minutes=1)`
   - `execution_timeout: timedelta(minutes=15)`
4. **Empty Dataset Handling:**
   - If Bronze or Silver has 0 new records, tasks complete successfully with `rows_synced: 0` without failing the pipeline.

---

## 7. Local Execution & Infrastructure Strategy

Because the development environment is Windows:
1. **Containerized Airflow Option (Docker Compose):**
   - Apache Airflow natively requires POSIX APIs (`pwd`, `grp`, `fcntl`) for its webserver and scheduler processes, which are not native to Windows bare metal.
   - We will provide `docker-compose.airflow.yml` mounting the FinPulse repository (`./airflow`, `./data`, `./dbt`, `./src`, `./config`) to run Airflow 2.9+ with PostgreSQL backend.
2. **Direct Python Execution & Testing:**
   - To ensure fast, zero-dependency testing on Windows, all task logic will reside in standard importable Python modules (`src/finpulse/orchestration/tasks.py`).
   - The DAG definition in `airflow/dags/finpulse_pipeline.py` will import these callables.
   - Comprehensive unit and integration tests in `tests/unit/test_airflow_dag.py` will test DAG loading, task dependencies, operator signatures, and execution without needing a running daemon.

---

## 8. Testing & Verification Strategy

We will implement test suites covering:
1. **DAG Integrity Test:** Verifies DAG loads with zero syntax or import errors and contains exactly the 5 specified tasks.
2. **Dependency Structure Test:** Verifies `bronze_ingestion >> silver_transformation >> warehouse_sync >> dbt_transformations >> data_quality_validation`.
3. **Task Execution Tests:** Tests each Python callable with mocked and live components.
4. **Failure Propagation Test:** Validates that a failure in an upstream stage halts downstream task execution.
5. **Full Project Test Suite:** Ensures all 132 existing unit and integration tests across Phases 1–7 continue to pass.

---

*Stage 1 Inspection & Architecture Proposal complete. Awaiting user review and approval before proceeding to Stage 2.*

