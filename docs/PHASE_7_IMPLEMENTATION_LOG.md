# FinPulse — Phase 7: Warehouse Architecture & Technical Specification

**Document Status:** Completed & Verified (Stages 1–5)  
**Target Milestone:** Phase 7 — Analytical Warehouse & dbt Transformation Layer  
**Engine:** DuckDB + dbt-duckdb  
**Upstream Dependency:** Phase 6 Silver Delta Lake (`data/lake/silver/transactions`)  
**Audit Date:** 2026-11-13  
**Auditor:** Antigravity Data Platform Agent  

---

## 1. Executive Summary & Objective

The objective of **Phase 7** is to design and implement a **local, zero-cost analytical data warehouse** for FinPulse. 

In earlier phases, incoming transactions were ingested (Phase 3), streamed via Kafka (Phase 4), stored in Bronze JSONL (Phase 5), and cleansed into an ACID Delta Lake Silver table (Phase 6). Phase 7 bridges the gap between raw curated events and analytical intelligence by establishing:
- **DuckDB** as the embedded, zero-cost analytical columnar database.
- **dbt-duckdb** for modular, tested, version-controlled SQL data modeling.
- **Gold Marts** delivering aggregated metrics on daily cashflows, monthly spending, merchant analytics, and inflows vs. outflows.

> [!NOTE]
> **Zero Cloud Cost Guarantee:** While the original project proposal mentioned Google BigQuery, BigQuery is kept completely optional. All core warehouse modeling, storage, and analytical queries are designed to execute locally with zero cloud dependencies or paid APIs.

---

## 2. Upstream Silver Layer Inspection

An inspection of the Phase 6 implementation at commit `fecf873` establishes the exact upstream data contract:

### A. Silver Table Path & Format
- **Table Location:** `data/lake/silver/transactions` (relative to repository root).
- **Format:** Delta Lake table containing Parquet data files and an ACID commit log in `data/lake/silver/transactions/_delta_log/`.
- **Writer Mechanism:** [`src/finpulse/silver/writer.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/silver/writer.py) writes records using PyArrow tables and `deltalake.write_deltalake` with merge upsert on `deduplication_key`.

### B. Upstream Schema & Data Types
Inspecting [`src/finpulse/common/models.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/common/models.py) and [`src/finpulse/silver/writer.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/silver/writer.py):

| Column Name | Python Type | Arrow Storage Type | Description |
| :--- | :--- | :--- | :--- |
| `transaction_id` | `str` | `pa.string()` | Deterministic transaction identifier. |
| `user_id` | `str` | `pa.string()` | User account identifier. |
| `amount` | `Decimal` | `pa.decimal128(18, 2)` | Positive monetary amount (never float). |
| `currency` | `str` | `pa.string()` | 3-letter currency code (e.g. `INR`). |
| `direction` | `str` | `pa.string()` | Transaction direction (`DEBIT` or `CREDIT`). |
| `transaction_timestamp` | `datetime` | `pa.timestamp("us", tz="UTC")` | UTC transaction timestamp. |
| `merchant_raw` | `str \| None` | `pa.string()` (nullable) | Raw extracted merchant name. |
| `merchant_normalized` | `str \| None` | `pa.string()` (nullable) | Standardized merchant entity (e.g. `Amazon`, `Uber`). |
| `reference_id` | `str \| None` | `pa.string()` (nullable) | External UPI/Bank reference number. |
| `source_type` | `str` | `pa.string()` | Origin (`BANK_SMS`, `UPI_CSV`, `CARD_PDF`, `MANUAL`). |
| `deduplication_key` | `str` | `pa.string()` | Hash fingerprint for deduplication. |
| `processed_at` | `datetime` | `pa.timestamp("us", tz="UTC")` | Silver processing timestamp. |
| `schema_version` | `str` | `pa.string()` | Schema version (`1.0`). |

---

## 3. Warehouse Architecture Proposal

```
[ Silver Delta Lake ] (data/lake/silver/transactions/)
          │
          ▼
 [ DuckDB Loader / Scan ] (src/finpulse/warehouse/loader.py)
          │
          ▼
   [ DuckDB Warehouse ] (data/warehouse/finpulse.duckdb)
          │
          ├──────────────────────────────────────────────────────┐
          ▼                                                      ▼
  [ dbt Staging Layer ] (stg_transactions.sql)         [ dbt Lineage & Docs ]
          │
          ▼
[ dbt Intermediate Layer ] (int_daily_transactions.sql)
          │
          ├─────────────────────────┬────────────────────────────┐
          ▼                         ▼                            ▼
[ Mart: Daily Spending ]  [ Mart: Monthly Trends ]   [ Mart: Merchant Analytics ]
(gold_daily_spending)     (gold_monthly_spending)   (gold_merchant_spending)
          │                         │                            │
          └─────────────────────────┼────────────────────────────┘
                                    ▼
                         [ Mart: Cashflow Summary ]
                         (gold_cashflow_summary)
                                    │
                                    ▼
                         [ Phase 9: Dashboard ]
                         (Streamlit / Analytics)
```

### A. Database Storage Location
* File path: `data/warehouse/finpulse.duckdb`
* Fast embedded storage, persistent on local disk, ACID transactional, zero memory bloat, native Parquet/Arrow execution engine.

### B. Silver-to-DuckDB Ingestion Strategy
Two possible integration patterns were evaluated:
1. **Option A: DuckDB Native `delta_scan` Extension:**
   - Syntax: `SELECT * FROM delta_scan('data/lake/silver/transactions')`
   - *Limitation:* DuckDB's `delta` extension requires an active internet connection to install on first run (`INSTALL delta; LOAD delta;`). In isolated or Windows environments without pre-cached binaries, this can introduce installation hurdles.
2. **Option B: Python-Assisted Loader (`src/finpulse/warehouse/loader.py`) [RECOMMENDED]:**
   - FinPulse already has `deltalake` installed and operational in Python.
   - The loader reads the Delta table via `DeltaTable("data/lake/silver/transactions").to_pyarrow_table()`.
   - The PyArrow table is registered directly in DuckDB and written to a DuckDB table or view (`silver_transactions`).
   - *Advantage:* 100% offline, zero network dependencies, exact decimal precision preservation, deterministic on Windows NTFS.
3. **Option C: Hybrid Approach in dbt-duckdb:**
   - Configure dbt source to read directly from the DuckDB table created by `loader.py` or through a Parquet view.

---

## 4. dbt Project Structure & Layered Modeling

The `dbt/` folder will be structured according to modern analytics engineering standards:

```text
dbt/
├── dbt_project.yml              # Project configuration & model materializations
├── profiles.yml                 # DuckDB connection profile
└── models/
    ├── staging/
    │   ├── schema.yml           # Sources & column-level testing
    │   └── stg_transactions.sql # Canonical transaction staging view
    ├── intermediate/
    │   ├── schema.yml
    │   └── int_daily_transactions.sql # Daily rollups and calendar spine joins
    └── marts/
        ├── schema.yml           # Gold model documentation & business tests
        ├── gold_daily_spending.sql    # Daily net flows and transaction counts
        ├── gold_monthly_spending.sql  # Monthly aggregates and savings rates
        ├── gold_merchant_spending.sql # Top merchants, frequency, ticket size
        └── gold_cashflow_summary.sql  # Inflow vs outflow ratio & volume share
```

### A. Staging Layer (`stg_transactions.sql`)
- **Materialization:** `view`
- **Purpose:** Clean 1:1 view over Silver transactions with explicit column aliases, casting, and calendar extractions.
- **SQL Logic:**
  ```sql
  select
      transaction_id,
      user_id,
      cast(amount as decimal(18, 2)) as amount,
      upper(trim(currency)) as currency,
      direction,
      transaction_timestamp,
      cast(transaction_timestamp as date) as transaction_date,
      date_trunc('month', transaction_timestamp) as transaction_month,
      coalesce(merchant_normalized, merchant_raw, 'Unknown') as merchant_name,
      merchant_raw,
      merchant_normalized,
      reference_id,
      source_type,
      deduplication_key,
      processed_at
  from {{ source('silver', 'transactions') }}
  ```

### B. Intermediate Layer (`int_daily_transactions.sql`)
- **Materialization:** `view`
- **Purpose:** Pre-aggregates daily metrics by `user_id`, `transaction_date`, `currency`, and `direction`, separating debits (expenses) and credits (income).

### C. Gold Analytical Marts (`marts/`)
1. **`gold_daily_spending.sql` (Daily Spending Summary):**
   - **Grain:** `(user_id, transaction_date, currency)`
   - **Metrics:** `total_debit_amount`, `total_credit_amount`, `net_cash_flow`, `debit_count`, `credit_count`, `total_transactions`.
2. **`gold_monthly_spending.sql` (Monthly Spending Summary):**
   - **Grain:** `(user_id, transaction_month, currency)`
   - **Metrics:** `monthly_expenses`, `monthly_income`, `net_savings`, `savings_rate_pct`, `daily_avg_spend`.
3. **`gold_merchant_spending.sql` (Merchant Analytics):**
   - **Grain:** `(user_id, merchant_name, currency)`
   - **Metrics:** `total_spend`, `transaction_count`, `avg_ticket_size`, `first_purchase_date`, `last_purchase_date`.
4. **`gold_cashflow_summary.sql` (Cashflow & Volume Analysis):**
   - **Grain:** `(user_id, direction, currency)`
   - **Metrics:** `total_volume`, `transaction_count`, `percentage_of_total_volume`.
5. **`gold_category_spending.sql` (Category Analytics):**
   - **Status:** *Pending Phase 6 Categorization*.
   - **Architecture Strategy:** The model structure is designed to aggregate by `category`. Until the Phase 6 categorization module is implemented, this model will fall back to `'UNCATEGORIZED'` or derive simple heuristics from `merchant_name`.

---

## 5. Technical Decisions & Trade-Offs

| Decision Area | Selected Approach | Alternatives Evaluated | Rationale |
| :--- | :--- | :--- | :--- |
| **Warehouse Engine** | **DuckDB** | BigQuery, SQLite, PostgreSQL | Embedded, zero cloud cost, serverless, native vectorized Arrow execution, 100x faster than SQLite for OLAP. |
| **Transformation Tool**| **dbt-duckdb** | Raw Python SQL scripts, dbt-bigquery | Industry standard for DAG resolution, model documentation, lineage tracking, and automated data testing. |
| **Silver Ingestion** | **Python Loader (`loader.py`)** | DuckDB `delta_scan` extension | Pre-installed `deltalake` in Python guarantees zero network downloads, runs cleanly offline on Windows NTFS. |
| **Decimal Precision**| **`DECIMAL(18, 2)`** | `FLOAT`, `DOUBLE` | Strict requirement for financial compliance; guarantees exact cent precision without IEEE 754 float drift. |
| **Timestamp Timezone**| **`TIMESTAMPTZ` (UTC)** | Local naive datetime | Enforces timezone-aware UTC timestamps end-to-end. |
| **Testing Strategy** | **dbt generic & custom tests** | Great Expectations | Built-in dbt tests (`unique`, `not_null`, `accepted_values`, `positive_amount`) run directly in DuckDB with zero extra tooling. |

---

## 6. Implementation & Verification Audit (Stages 2–5)

All implementation stages of Phase 7 are fully complete and verified:

### A. Stage 2: Warehouse Infrastructure & Ingestion Module
- **Dependencies:** Configured in `pyproject.toml` under `[project.optional-dependencies] warehouse` with `duckdb>=1.1` and `dbt-duckdb>=1.8`.
- **Loader Implementation:** [`src/finpulse/warehouse/loader.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/warehouse/loader.py)
  - `WarehouseLoader` class connects to DuckDB at `data/warehouse/finpulse.duckdb`.
  - Reads Delta Lake table at `data/lake/silver/transactions` via `DeltaTable.to_pyarrow_table()`.
  - Creates schema `silver` and overwrites `silver.transactions` idempotently.
  - Gracefully handles absent or empty Delta Lake tables by creating an empty table matching the PyArrow schema.

### B. Stage 3 & 4: dbt Configuration & Data Models
- **Project Configuration:** [`dbt/dbt_project.yml`](file:///d:/FinpulseDE/FinPulse/dbt/dbt_project.yml) and [`dbt/profiles.yml`](file:///d:/FinpulseDE/FinPulse/dbt/profiles.yml).
- **Models Created:**
  1. `stg_transactions` (`dbt/models/staging/stg_transactions.sql`): Materialized as `view`. Exposes canonical columns, casts `amount` as `DECIMAL(18, 2)`, extracts `transaction_date` and `transaction_month`.
  2. `int_daily_transactions` (`dbt/models/intermediate/int_daily_transactions.sql`): Materialized as `view`. Daily aggregations split by debit and credit volumes.
  3. `gold_daily_spending` (`dbt/models/marts/gold_daily_spending.sql`): Materialized as `table`. Metrics: `total_debit_amount`, `total_credit_amount`, `net_cash_flow`, `debit_count`, `credit_count`, `total_transactions`.
  4. `gold_monthly_spending` (`dbt/models/marts/gold_monthly_spending.sql`): Materialized as `table`. Metrics: `monthly_expenses`, `monthly_income`, `net_savings`, `savings_rate_pct`, `daily_avg_spend`.
  5. `gold_merchant_spending` (`dbt/models/marts/gold_merchant_spending.sql`): Materialized as `table`. Focuses on debit outflow to merchants, average ticket size, and first/last purchase timestamps.
  6. `gold_cashflow_summary` (`dbt/models/marts/gold_cashflow_summary.sql`): Materialized as `table`. Summarizes transaction volumes and percentage shares by direction (`DEBIT` vs. `CREDIT`).
  7. `gold_category_spending` (`dbt/models/marts/gold_category_spending.sql`): Materialized as `table`. Heuristic category assignment (`Food & Groceries`, `Travel & Commute`, `Shopping`, `Utilities & Bills`, `Entertainment`) with fallback to `Other Expenses`.
- **dbt Testing:** 27 automated tests configured across `schema.yml` files (unique keys, not-null constraints, accepted values for directions and match statuses, and positive amount checks).

### C. Stage 5: Warehouse Pipeline Runner & Integration
- **Pipeline Implementation:** [`src/finpulse/warehouse/pipeline.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/warehouse/pipeline.py)
  - `run_warehouse_pipeline()` orchestrates:
    1. Silver $\rightarrow$ DuckDB sync via `WarehouseLoader`.
    2. dbt compilation and model execution via `dbtRunner().invoke(["run"])`.
    3. dbt automated data test execution via `dbtRunner().invoke(["test"])`.
- **CLI Script:** [`scripts/run_warehouse.py`](file:///d:/FinpulseDE/FinPulse/scripts/run_warehouse.py) providing CLI arguments for `--silver-path`, `--db-path`, `--project-dir`, and `--profiles-dir`.
- **Test Suite:**
  - Unit tests: [`tests/unit/test_warehouse_loader.py`](file:///d:/FinpulseDE/FinPulse/tests/unit/test_warehouse_loader.py) testing empty table handling, table population, and sync idempotency.
  - Integration tests: [`tests/integration/test_warehouse_pipeline.py`](file:///d:/FinpulseDE/FinPulse/tests/integration/test_warehouse_pipeline.py) creating a synthetic Delta Lake table, executing the complete pipeline, running 27 dbt tests, and asserting analytical metrics across all 5 Gold Marts.
- **Verification Results:**
  - `ruff check .`: All checks passed.
  - `pytest`: **132 passed, 0 failures, 0 errors** in 20s.

---

## 7. Known Risks & Mitigation

1. **DuckDB Concurrency on Windows:** DuckDB supports multiple readers but a single writer process. Ensure ETL scripts (`loader.py` and `dbt`) close connections before analytical readers attach.
2. **Missing Phase 6 Categorization:** `gold_category_spending` cannot report meaningful spend categories until transaction categorization is implemented. A documented fallback (`UNCATEGORIZED`) prevents pipeline failure.
3. **Delta Table Compaction:** Because `deltalake` merges create new parquet files, DuckDB must always read the table through the Delta transaction log rather than raw file globs to avoid reading superseded rows.

---

*Phase 7 Stage 1 Architecture Inspection is complete and ready for review.*

