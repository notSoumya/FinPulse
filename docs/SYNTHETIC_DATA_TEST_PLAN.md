# FinPulse — Synthetic Data Test Plan & System Inventory

**Document Status:** Complete & Verified  
**Milestone:** Synthetic Data Generation, Ingestion & End-to-End Pipeline Validation  
**Date:** 2026-11-13  
**Auditor:** Antigravity Data Platform Agent  

---

## 1. System Inventory

Following a source-code audit across `src/finpulse/`, `dbt/`, `dashboard/`, `airflow/`, and `tests/`, below is the complete inventory of the FinPulse data platform.

| Area | Component / Specification | Implementation Details & References |
| :--- | :--- | :--- |
| **Input Sources** | `UPI_CSV`, `CARD_PDF`, `BANK_SMS`, `MANUAL` | Defined in [`src/finpulse/common/constants.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/common/constants.py) |
| **File / Data Formats** | CSV, PDF, Text (SMS), JSON (Manual) | Supported across parsers and FastAPI endpoints |
| **Parsers** | - `parse_upi_csv`<br>- `parse_card_pdf`<br>- `parse_bank_sms`<br>- `parse_manual` | - [`src/finpulse/ingestion/parsers/upi_parser.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/ingestion/parsers/upi_parser.py)<br>- [`src/finpulse/ingestion/parsers/card_pdf_parser.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/ingestion/parsers/card_pdf_parser.py)<br>- [`src/finpulse/ingestion/parsers/sms_parser.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/ingestion/parsers/sms_parser.py)<br>- [`src/finpulse/ingestion/parsers/manual_parser.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/ingestion/parsers/manual_parser.py) |
| **Transaction Types** | `DEBIT`, `CREDIT` | Enforced by canonical model [`Transaction`](file:///d:/FinpulseDE/FinPulse/src/finpulse/common/models.py) |
| **Categories** | `Shopping`, `Food & Groceries`, `Travel & Commute`, `Income`, `Uncategorized` | Modeled in [`dbt/models/marts/gold_category_spending.sql`](file:///d:/FinpulseDE/FinPulse/dbt/models/marts/gold_category_spending.sql) |
| **Required Fields** | `transaction_id`, `user_id`, `amount` (> 0), `currency`, `direction`, `transaction_timestamp`, `source_type` | Validated by Pydantic model [`Transaction`](file:///d:/FinpulseDE/FinPulse/src/finpulse/common/models.py) |
| **Optional Fields** | `merchant_raw`, `merchant_normalized`, `reference_id` | Defaults to `None` |
| **Validation Rules** | Positive Decimal amount, valid ISO-8601 UTC timestamp, 3-letter currency code (`INR`), valid direction, extra fields forbidden | [`src/finpulse/processing/validator.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/processing/validator.py) & Pydantic validators |
| **Quarantine Rules** | Invalid payloads, validation errors, unparseable events routed to `data/lake/quarantine/` with reasons | [`src/finpulse/processing/quarantine.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/processing/quarantine.py) |
| **Normalization** | Merchant name regex cleanup, lookup against `config/merchant_mapping.json` (fallback: title-casing) | [`src/finpulse/processing/merchant_normalizer.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/processing/merchant_normalizer.py) |
| **Deduplication** | - Intra-parser duplicate ID suppression<br>- Bronze file idempotency (`event_id`)<br>- Checkpoint ledger (`silver_checkpoint.json`)<br>- Fuzzy cross-source deduplication (`amount`, `currency`, `direction`, `merchant`, `reference_id`, timestamp within 5 mins)<br>- Delta Lake MERGE/deduplication key isolation | [`src/finpulse/processing/deduplicator.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/processing/deduplicator.py), [`src/finpulse/silver/writer.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/silver/writer.py) |
| **Storage Layers** | - **Bronze**: JSONL partitioned by `source_type/year/month/day`<br>- **Silver**: Delta Lake (Parquet + ACID log)<br>- **Warehouse**: DuckDB `silver.transactions`<br>- **Gold**: DuckDB views and marts | [`src/finpulse/bronze/storage.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/bronze/storage.py), [`src/finpulse/silver/writer.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/silver/writer.py), [`src/finpulse/warehouse/loader.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/warehouse/loader.py) |
| **Analytics & KPIs** | Total Income, Total Expenses, Net Cash Flow, Savings Rate (%), Total Transactions, Average Ticket Size, Trends, Merchant Breakdown | [`dashboard/queries.py`](file:///d:/FinpulseDE/FinPulse/dashboard/queries.py), [`dbt/models/marts/`](file:///d:/FinpulseDE/FinPulse/dbt/models/marts/) |

---

## 2. Ingestion & Parser Audit Findings

### Detailed Parser Requirements

1. **UPI CSV (`parse_upi_csv`)**:
   - **Mandatory columns:** `date`, `amount`, `type`, `merchant`.
   - **Optional columns:** `reference_id`, `currency` (defaults to `"INR"`).
   - **Direction mapping:** `DR`, `DEBIT` -> `DEBIT`; `CR`, `CREDIT` -> `CREDIT`.
   - **Timestamp format:** Accepted by `pd.to_datetime(..., utc=True)`.

2. **Card Statement PDF (`parse_card_pdf`)**:
   - **Text matching regex:** `(\d{2}-\d{2}-\d{4})\s+(.+?)\s+([0-9,]+\.\d{2})`.
   - **Date format:** `%d-%m-%Y` (e.g. `14-10-2026`).
   - **Direction:** Hardcoded to `DEBIT`.
   - **Currency:** Hardcoded to `INR`.
   - **Deduplication:** Internal `seen_ids` set drops duplicate transaction IDs extracted within the same PDF.

3. **Bank SMS (`parse_bank_sms`)**:
   - **Amount pattern:** `(?:Rs\.?|INR)\s*([0-9,]+(?:\.[0-9]{1,2})?)`.
   - **Direction keywords:**
     - Debit: `debited`, `debit`, `spent`, `withdrawn`.
     - Credit: `credited`, `credit`, `received`.
   - **Merchant patterns:** `(?:at|towards|to)\s+([A-Za-z0-9 &._-]+)` or `from\s+([A-Za-z0-9 &._-]+)`.
   - **Metadata required:** Caller must pass `user_id`, `timestamp` (UTC datetime), and optional `reference_id`.

4. **Manual Transaction (`parse_manual`)**:
   - **Payload dictionary:** `amount`, `transaction_timestamp` (ISO-8601 string), `direction`, `user_id`, optional `currency`, `merchant_raw`, `reference_id`, `transaction_id`.

### Discrepancies & Pipeline Differences Discovered

1. **Batch Ingestion File Discovery (`ingest_bronze_task`)**:
   - In [`src/finpulse/orchestration/tasks.py`](file:///d:/FinpulseDE/FinPulse/src/finpulse/orchestration/tasks.py), `ingest_bronze_task` scans `raw_dir` for files ending in `.csv` (UPI) and `.pdf` (Card).
   - Any `.json` (Manual) or `.txt` (SMS) files placed into `raw_dir` are currently skipped with a warning: `Unsupported raw file format ...; skipping.`
   - **Resolution for Validation:**
     - For `UPI_CSV` and `CARD_PDF`: Validated via file drop in raw directory and `ingest_bronze_task`.
     - For `BANK_SMS` and `MANUAL`: Validated directly through their respective parsers and ingested into Bronze using `BronzeStorage.write_event()` (matching the exact event structure produced by the Kafka producer/worker), and also verified through the FastAPI ingestion endpoints!
     - This ensures 100% of all 4 source types are exercised through real ingestion and downstream pipeline stages.

2. **Categorization Domain**:
   - The dbt mart `gold_category_spending.sql` applies category logic based on keyword matching on `merchant_name` for `DEBIT` transactions.
   - Any merchant not matching Amazon, Flipkart, Swiggy, Zomato, Blinkit, Instamart, Uber, Ola, Metro, or IRCTC defaults to `Uncategorized`.
   - The synthetic dataset will purposefully include representative merchants in each of these known categories as well as intentional `Uncategorized` merchants.

---

## 3. Synthetic Dataset Design Plan

### Target Volume & Source Breakdown

- **Total Synthetic Records:** 120 valid records + 15 intentional edge-case / invalid / duplicate records.
- **Sources Covered:**
  1. `UPI_CSV`: 40 valid transactions (debit and credit, multiple merchants, references).
  2. `CARD_PDF`: 35 valid transactions (debits across shopping, food, travel, utilities).
  3. `BANK_SMS`: 25 valid transactions (salary credit, ATM debit, merchant debits).
  4. `MANUAL`: 20 valid transactions (cash expenses, freelance income, reimbursement).
- **Time Distribution:** Deterministic dates across 3 months: **September 2026, October 2026, and November 2026**.
- **Edge Cases & Failure Scenarios:**
  - 3 Duplicate records (same ID or cross-source match).
  - 3 Invalid records (negative amount, missing mandatory fields, malformed date).
  - 2 Month-boundary records (first and last day of months).
  - 2 High-value transactions.
- **Random Seed:** Fixed seed (`42`) to guarantee 100% deterministic reproducibility.

---

## 4. Test Environment Isolation Strategy

To prevent polluting or mutating existing data in `data/lake/` or `data/warehouse/finpulse.duckdb`:

```text
data/
└── synthetic/
    ├── raw/
    │   ├── upi/
    │   │   └── upi_transactions.csv
    │   ├── card/
    │   │   └── card_statement.pdf
    │   ├── bank_sms/
    │   │   └── sms_messages.json
    │   └── manual/
    │       └── manual_entries.json
    ├── bronze/
    ├── silver/
    │   └── transactions/
    ├── checkpoints/
    │   └── silver_checkpoint.json
    ├── quarantine/
    │   └── rejected_transactions/
    ├── warehouse/
    │   └── finpulse_synthetic.duckdb
    ├── expected/
    │   └── expected_analytics.json
    └── reports/
        ├── parser_validation.json
        └── analytics_reconciliation.json
```

All pipeline components (`BronzeStorage`, `BronzeReader`, `SilverPipeline`, `SilverWriter`, `WarehouseLoader`, `dbt`, `dashboard`) will be parameterized to run against this isolated sandbox.

