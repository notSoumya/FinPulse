
# FinPulse — Shared Data Contract

Version: 1.0

## 1. Purpose

This document defines the canonical transaction structure
used throughout FinPulse.

All team members must follow this contract.

## 2. Supported Sources

- BANK_SMS
- UPI_CSV
- CARD_PDF
- MANUAL

## 3. Canonical Transaction Schema

| Field | Type | Required | Description |
|---|---|---|---|
| transaction_id | String | Yes | Canonical transaction identifier |
| user_id | String | Yes | User identifier |
| amount | Decimal | Yes | Positive transaction amount |
| currency | String | Yes | Three-letter currency code |
| direction | Enum | Yes | DEBIT or CREDIT |
| transaction_timestamp | Datetime | Yes | Timezone-aware transaction timestamp |
| merchant_raw | String | No | Original merchant name |
| merchant_normalized | String | No | Standardized merchant name |
| reference_id | String | No | Bank or UPI reference |
| source_type | Enum | Yes | Origin of transaction |

## 4. Business Rules

1. Amount must always be greater than zero.
2. DEBIT and CREDIT determine transaction direction.
3. Timestamps must contain timezone information.
4. All timestamps are converted to UTC.
5. Currency must contain three alphabetic characters.
6. Original merchant names must be preserved.
7. Missing reference IDs are allowed.
8. Unknown fields are rejected.

## 5. Transaction ID Rules

- Prefer a stable source reference when available.
- Otherwise generate a deterministic hash from transaction attributes.
- Cross-source duplicate detection is handled separately.
- Event IDs and transaction IDs are different concepts.

## 6. Team Responsibilities

### Member 1 — Ingestion
- Parse source-specific formats.
- Convert records into canonical transactions.
- Validate transactions using the shared model.

### Member 2 — Data Platform
- Consume validated events.
- Store original records in Bronze.
- Normalize and deduplicate transactions.
- Track rejected and duplicate records.

### Member 3 — Warehouse
- Map canonical fields into BigQuery.
- Build dbt models.
- Preserve the agreed field names and data types.

## 7. Schema Change Policy

Any modification to this contract must be discussed
and approved by all three team members.

Changes must include updated tests and documentation.

## 8. Schema Version

Current version: 1.0
