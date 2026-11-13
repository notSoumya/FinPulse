# FinPulse — Synthetic Data Generation Log

**Document Status:** Complete & Verified  
**Milestone:** Synthetic Data Generation, Ingestion & End-to-End Pipeline Validation  
**Date:** 2026-11-13  
**Auditor:** Antigravity Data Platform Agent  

---

## 1. Generation Parameters & Environment

- **Random Seed:** `42` (Fixed for deterministic reproducibility across runs)
- **Primary Test User:** `synthetic_user_1`
- **Secondary Test User (Multi-tenant):** `synthetic_user_2`
- **Calendar Time Span:** September 1, 2026 to November 15, 2026 (3 distinct calendar months)
- **Output Base Directory:** [`data/synthetic/`](file:///d:/FinpulseDE/FinPulse/data/synthetic/)
- **Generator Script:** [`tests/fixtures/synthetic_data/generate_synthetic_data.py`](file:///d:/FinpulseDE/FinPulse/tests/fixtures/synthetic_data/generate_synthetic_data.py)
- **Manifest Location:** [`data/synthetic/manifest.json`](file:///d:/FinpulseDE/FinPulse/data/synthetic/manifest.json)

---

## 2. Generated Source Files & Volume Breakdown

| Input Source | Generated File Path | Valid Records | Edge / Invalid Records | Format & Specifications |
| :--- | :--- | :---: | :---: | :--- |
| **UPI Statement** | [`data/synthetic/raw/upi/upi_transactions.csv`](file:///d:/FinpulseDE/FinPulse/data/synthetic/raw/upi/upi_transactions.csv) | 40 | 3 | CSV with headers `date,amount,type,merchant,reference_id,currency`. Tests `DR`/`CR`/`DEBIT`/`CREDIT`. |
| **UPI Edge Cases** | [`data/synthetic/raw/upi/upi_edge_cases.csv`](file:///d:/FinpulseDE/FinPulse/data/synthetic/raw/upi/upi_edge_cases.csv) | — | 3 | Missing amount, unknown direction type, duplicate reference ID. |
| **Card Statement** | [`data/synthetic/raw/card/card_statement.pdf`](file:///d:/FinpulseDE/FinPulse/data/synthetic/raw/card/card_statement.pdf) | 35 | 2 | Real binary PDF generated with PyMuPDF (`fitz`), parsed via `pdfplumber`. Contains formatted lines `(\d{2}-\d{2}-\d{4})\s+(.+?)\s+([0-9,]+\.\d{2})`. Includes internal repeated duplicate line and non-transaction text noise. |
| **Bank SMS** | [`data/synthetic/raw/bank_sms/bank_sms.json`](file:///d:/FinpulseDE/FinPulse/data/synthetic/raw/bank_sms/bank_sms.json) | 25 | 2 | JSON list of SMS text payloads. Includes salary credits, merchant spends, ATM withdrawals, and transfers. |
| **Bank SMS Edge Cases**| [`data/synthetic/raw/bank_sms/bank_sms_edge_cases.json`](file:///d:/FinpulseDE/FinPulse/data/synthetic/raw/bank_sms/bank_sms_edge_cases.json) | — | 2 | Missing amount, ambiguous direction keywords. |
| **Manual Entries** | [`data/synthetic/raw/manual/manual_transactions.json`](file:///d:/FinpulseDE/FinPulse/data/synthetic/raw/manual/manual_transactions.json) | 20 | 3 | JSON manual payloads with timestamps, merchant raw, and reference IDs. |
| **Manual Edge Cases** | [`data/synthetic/raw/manual/manual_edge_cases.json`](file:///d:/FinpulseDE/FinPulse/data/synthetic/raw/manual/manual_edge_cases.json) | — | 3 | Negative amount, missing direction, invalid ISO timestamp. |
| **TOTALS** | — | **120** | **15** | Fully balanced across spending categories, directions, and months. |

---

## 3. Financial Dimensions & Distribution

### 3.1 Directional Distribution (Primary User: `synthetic_user_1`)
- **Total Valid Records:** 106
- **Debit Transactions (Outflows):** 94 records totaling **₹120,563.00**
- **Credit Transactions (Inflows):** 12 records totaling **₹227,900.00**
- **Net Cash Flow:** **₹107,337.00**
- **Savings Rate (%):** **47.10%**

### 3.2 Monthly Spending Distribution
- **September 2026:**
  - Income: ₹103,500.00 (Salary ₹85,000 + Friends/Freelance ₹18,500)
  - Expenses: ₹32,417.50 (33 transactions)
  - Net: +₹71,082.50
- **October 2026:**
  - Income: ₹116,500.00 (Salary ₹85,000 + Reimbursements/Stipends ₹31,500)
  - Expenses: ₹41,007.50 (41 transactions)
  - Net: +₹75,492.50
- **November 2026:**
  - Income: ₹7,900.00 (Cashback + Refunds)
  - Expenses: ₹47,138.00 (32 transactions)
  - Net: -₹39,238.00

### 3.3 Spending Category Breakdown (DEBIT Outflows)
- **Shopping:** ₹49,983.00 (16 transactions) — Amazon, Flipkart
- **Food & Groceries:** ₹24,510.50 (34 transactions) — Swiggy, Zomato, Blinkit, Instamart
- **Travel & Commute:** ₹7,189.50 (20 transactions) — Uber, Ola, Metro, IRCTC
- **Uncategorized:** ₹38,880.00 (24 transactions) — Reliance Digital, D-Mart, Chai Point, Hardware, Books

---

## 4. Multi-Tenant User Distribution

To verify user-level tenant isolation across dbt marts and dashboard filters:
- **`synthetic_user_1` (Primary):** 106 transactions across all 4 sources.
- **`synthetic_user_2` (Secondary):** 14 transactions (4 UPI, 3 Card, 3 SMS, 4 Manual) totaling ₹97,000.00 income and ₹8,730.00 expenses.

