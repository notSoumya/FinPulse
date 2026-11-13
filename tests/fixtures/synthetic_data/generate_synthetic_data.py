"""
Synthetic Financial Data Generator for FinPulse End-to-End Validation.

Generates reproducible, fictional financial records across all 4 supported sources:
- UPI CSV (date, amount, type, merchant, reference_id, currency)
- Card Statement PDF (parseable PyMuPDF statement text matching regex)
- Bank SMS (JSON list of SMS messages with direction keywords & amounts)
- Manual Transactions (JSON list of manual transaction payloads)

Includes:
- Fictional merchants and references
- 3 distinct calendar months (Sep 2026, Oct 2026, Nov 2026)
- Controlled debits and credits
- Deterministic random seed (42)
- Deliberate duplicates and invalid edge-case records
- Complete manifest and precomputed expected totals
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class SyntheticConfig:
    output_dir: Path = Path("data/synthetic")
    user_id: str = "synthetic_user_1"
    secondary_user_id: str = "synthetic_user_2"
    seed: int = 42


def get_upi_records(cfg: SyntheticConfig) -> tuple[list[dict], list[dict]]:
    """Return (valid_records, edge_case_records) for UPI CSV."""
    valid = [
        # September 2026
        {
            "date": "2026-09-02 10:15:00",
            "amount": "450.00",
            "type": "DEBIT",
            "merchant": "Swiggy",
            "reference_id": "UPI26090201",
            "currency": "INR",
        },
        {
            "date": "2026-09-03 14:20:00",
            "amount": "120.00",
            "type": "DR",
            "merchant": "Chai Point",
            "reference_id": "UPI26090301",
            "currency": "INR",
        },
        {
            "date": "2026-09-05 18:30:00",
            "amount": "1850.00",
            "type": "DEBIT",
            "merchant": "D-Mart",
            "reference_id": "UPI26090501",
            "currency": "INR",
        },
        {
            "date": "2026-09-08 09:00:00",
            "amount": "250.00",
            "type": "DEBIT",
            "merchant": "Uber India",
            "reference_id": "UPI26090801",
            "currency": "INR",
        },
        {
            "date": "2026-09-10 20:00:00",
            "amount": "620.00",
            "type": "DR",
            "merchant": "Zomato",
            "reference_id": "UPI26091001",
            "currency": "INR",
        },
        {
            "date": "2026-09-12 11:45:00",
            "amount": "2499.00",
            "type": "DEBIT",
            "merchant": "Amazon",
            "reference_id": "UPI26091201",
            "currency": "INR",
        },
        {
            "date": "2026-09-15 13:10:00",
            "amount": "340.00",
            "type": "DEBIT",
            "merchant": "Swiggy Instamart",
            "reference_id": "UPI26091501",
            "currency": "INR",
        },
        {
            "date": "2026-09-18 16:30:00",
            "amount": "5000.00",
            "type": "CREDIT",
            "merchant": "Friend Transfer",
            "reference_id": "UPI26091801",
            "currency": "INR",
        },
        {
            "date": "2026-09-21 08:20:00",
            "amount": "180.00",
            "type": "DR",
            "merchant": "Uber Trip",
            "reference_id": "UPI26092101",
            "currency": "INR",
        },
        {
            "date": "2026-09-25 19:15:00",
            "amount": "990.00",
            "type": "DEBIT",
            "merchant": "Blinkit",
            "reference_id": "UPI26092501",
            "currency": "INR",
        },
        {
            "date": "2026-09-28 12:00:00",
            "amount": "3500.00",
            "type": "CR",
            "merchant": "Cashback Bonus",
            "reference_id": "UPI26092801",
            "currency": "INR",
        },
        {
            "date": "2026-09-30 14:00:00",
            "amount": "550.00",
            "type": "DEBIT",
            "merchant": "Zomato",
            "reference_id": "UPI26093001",
            "currency": "INR",
        },
        # October 2026
        {
            "date": "2026-10-01 10:00:00",
            "amount": "780.00",
            "type": "DEBIT",
            "merchant": "Swiggy",
            "reference_id": "UPI26100101",
            "currency": "INR",
        },
        {
            "date": "2026-10-03 15:30:00",
            "amount": "310.00",
            "type": "DR",
            "merchant": "Uber India",
            "reference_id": "UPI26100301",
            "currency": "INR",
        },
        {
            "date": "2026-10-06 18:45:00",
            "amount": "3200.00",
            "type": "DEBIT",
            "merchant": "Flipkart",
            "reference_id": "UPI26100601",
            "currency": "INR",
        },
        {
            "date": "2026-10-08 12:15:00",
            "amount": "450.00",
            "type": "DEBIT",
            "merchant": "Swiggy Instamart",
            "reference_id": "UPI26100801",
            "currency": "INR",
        },
        {
            "date": "2026-10-10 17:00:00",
            "amount": "150.00",
            "type": "DR",
            "merchant": "Metro Recharge",
            "reference_id": "UPI26101001",
            "currency": "INR",
        },
        {
            "date": "2026-10-12 20:30:00",
            "amount": "820.00",
            "type": "DEBIT",
            "merchant": "Zomato",
            "reference_id": "UPI26101201",
            "currency": "INR",
        },
        {
            "date": "2026-10-15 11:00:00",
            "amount": "12000.00",
            "type": "CREDIT",
            "merchant": "Project Reimbursement",
            "reference_id": "UPI26101501",
            "currency": "INR",
        },
        {
            "date": "2026-10-17 14:10:00",
            "amount": "650.00",
            "type": "DEBIT",
            "merchant": "D-Mart",
            "reference_id": "UPI26101701",
            "currency": "INR",
        },
        {
            "date": "2026-10-20 19:25:00",
            "amount": "490.00",
            "type": "DR",
            "merchant": "Blinkit",
            "reference_id": "UPI26102001",
            "currency": "INR",
        },
        {
            "date": "2026-10-22 09:40:00",
            "amount": "270.00",
            "type": "DEBIT",
            "merchant": "Ola Cabs",
            "reference_id": "UPI26102201",
            "currency": "INR",
        },
        {
            "date": "2026-10-25 16:50:00",
            "amount": "1599.00",
            "type": "DEBIT",
            "merchant": "Amazon Seller",
            "reference_id": "UPI26102501",
            "currency": "INR",
        },
        {
            "date": "2026-10-28 13:00:00",
            "amount": "380.00",
            "type": "DEBIT",
            "merchant": "Chai Point",
            "reference_id": "UPI26102801",
            "currency": "INR",
        },
        {
            "date": "2026-10-31 15:15:00",
            "amount": "920.00",
            "type": "DR",
            "merchant": "Swiggy",
            "reference_id": "UPI26103101",
            "currency": "INR",
        },
        # November 2026
        {
            "date": "2026-11-01 11:30:00",
            "amount": "540.00",
            "type": "DEBIT",
            "merchant": "Zomato",
            "reference_id": "UPI26110101",
            "currency": "INR",
        },
        {
            "date": "2026-11-02 16:00:00",
            "amount": "290.00",
            "type": "DR",
            "merchant": "Uber India",
            "reference_id": "UPI26110201",
            "currency": "INR",
        },
        {
            "date": "2026-11-04 18:20:00",
            "amount": "4500.00",
            "type": "DEBIT",
            "merchant": "Flipkart",
            "reference_id": "UPI26110401",
            "currency": "INR",
        },
        {
            "date": "2026-11-05 13:15:00",
            "amount": "760.00",
            "type": "DEBIT",
            "merchant": "Swiggy Instamart",
            "reference_id": "UPI26110501",
            "currency": "INR",
        },
        {
            "date": "2026-11-06 20:00:00",
            "amount": "350.00",
            "type": "DEBIT",
            "merchant": "IRCTC",
            "reference_id": "UPI26110601",
            "currency": "INR",
        },
        {
            "date": "2026-11-08 10:45:00",
            "amount": "1800.00",
            "type": "CREDIT",
            "merchant": "Refund Goods",
            "reference_id": "UPI26110801",
            "currency": "INR",
        },
        {
            "date": "2026-11-09 14:50:00",
            "amount": "1250.00",
            "type": "DEBIT",
            "merchant": "D-Mart",
            "reference_id": "UPI26110901",
            "currency": "INR",
        },
        {
            "date": "2026-11-10 17:30:00",
            "amount": "420.00",
            "type": "DR",
            "merchant": "Blinkit",
            "reference_id": "UPI26111001",
            "currency": "INR",
        },
        {
            "date": "2026-11-11 12:00:00",
            "amount": "199.00",
            "type": "DEBIT",
            "merchant": "Ola Cabs",
            "reference_id": "UPI26111101",
            "currency": "INR",
        },
        {
            "date": "2026-11-12 19:40:00",
            "amount": "880.00",
            "type": "DEBIT",
            "merchant": "Zomato",
            "reference_id": "UPI26111201",
            "currency": "INR",
        },
        {
            "date": "2026-11-13 15:10:00",
            "amount": "670.00",
            "type": "DEBIT",
            "merchant": "Swiggy",
            "reference_id": "UPI26111301",
            "currency": "INR",
        },
        # Secondary user (multi-tenant verification)
        {
            "date": "2026-10-14 10:00:00",
            "amount": "1500.00",
            "type": "DEBIT",
            "merchant": "Amazon",
            "reference_id": "UPI261014U2",
            "currency": "INR",
            "_user": cfg.secondary_user_id,
        },
        {
            "date": "2026-10-18 16:00:00",
            "amount": "450.00",
            "type": "DEBIT",
            "merchant": "Swiggy",
            "reference_id": "UPI261018U2",
            "currency": "INR",
            "_user": cfg.secondary_user_id,
        },
        {
            "date": "2026-11-05 12:00:00",
            "amount": "25000.00",
            "type": "CREDIT",
            "merchant": "Salary Credit",
            "reference_id": "UPI261105U2",
            "currency": "INR",
            "_user": cfg.secondary_user_id,
        },
        {
            "date": "2026-11-10 18:30:00",
            "amount": "890.00",
            "type": "DEBIT",
            "merchant": "Zomato",
            "reference_id": "UPI261110U2",
            "currency": "INR",
            "_user": cfg.secondary_user_id,
        },
    ]

    # Intentional duplicates & invalid records
    edge_cases = [
        # Exact duplicate of UPI26090201
        {
            "date": "2026-09-02 10:15:00",
            "amount": "450.00",
            "type": "DEBIT",
            "merchant": "Swiggy",
            "reference_id": "UPI26090201",
            "currency": "INR",
            "_edge": "exact_duplicate",
        },
        # Invalid: missing amount
        {
            "date": "2026-09-04 11:00:00",
            "amount": "INVALID_AMOUNT",
            "type": "DEBIT",
            "merchant": "Fail Merchant",
            "reference_id": "UPI_FAIL_1",
            "currency": "INR",
            "_edge": "invalid_amount",
        },
        # Invalid: unsupported type
        {
            "date": "2026-09-06 12:00:00",
            "amount": "500.00",
            "type": "UNKNOWN_TYPE",
            "merchant": "Fail Merchant 2",
            "reference_id": "UPI_FAIL_2",
            "currency": "INR",
            "_edge": "invalid_type",
        },
    ]
    return valid, edge_cases


def get_card_pdf_records(cfg: SyntheticConfig) -> tuple[list[dict], list[dict]]:
    """Return (valid_records, edge_case_records) for Credit Card PDF."""
    valid = [
        # September 2026
        {"date": "04-09-2026", "merchant": "AMZN PAYMENTS", "amount": "2,499.00"},
        {"date": "07-09-2026", "merchant": "UBER INDIA", "amount": "420.50"},
        {"date": "11-09-2026", "merchant": "SWIGGY LIMITED", "amount": "850.00"},
        {"date": "14-09-2026", "merchant": "FLIPKART INTERNET", "amount": "1,899.00"},
        {"date": "17-09-2026", "merchant": "ZOMATO RESTAURANT", "amount": "640.00"},
        {"date": "20-09-2026", "merchant": "AMAZON SELLER", "amount": "3,150.00"},
        {"date": "23-09-2026", "merchant": "BLINKIT COMMERCE", "amount": "920.00"},
        {"date": "26-09-2026", "merchant": "UBER TRIP", "amount": "310.00"},
        {"date": "29-09-2026", "merchant": "SWIGGY INSTAMART", "amount": "1,120.00"},
        {"date": "30-09-2026", "merchant": "RELIANCE RETAIL", "amount": "4,500.00"},
        # October 2026
        {"date": "02-10-2026", "merchant": "AMAZON INDIA", "amount": "5,499.00"},
        {"date": "04-10-2026", "merchant": "UBER INDIA", "amount": "380.00"},
        {"date": "07-10-2026", "merchant": "SWIGGY LIMITED", "amount": "740.00"},
        {"date": "09-10-2026", "merchant": "METRO COMMUTE", "amount": "200.00"},
        {"date": "11-10-2026", "merchant": "FLIPKART INTERNET", "amount": "2,250.00"},
        {"date": "13-10-2026", "merchant": "ZOMATO RESTAURANT", "amount": "950.00"},
        {"date": "16-10-2026", "merchant": "SWIGGY INSTAMART", "amount": "610.50"},
        {"date": "19-10-2026", "merchant": "AMZN PAYMENTS", "amount": "1,299.00"},
        {"date": "21-10-2026", "merchant": "OLA CABS", "amount": "430.00"},
        {"date": "24-10-2026", "merchant": "BLINKIT COMMERCE", "amount": "870.00"},
        {"date": "27-10-2026", "merchant": "D-MART SUPERMARKET", "amount": "3,840.00"},
        {"date": "29-10-2026", "merchant": "UBER TRIP", "amount": "290.00"},
        {"date": "31-10-2026", "merchant": "SWIGGY LIMITED", "amount": "1,050.00"},
        # November 2026
        {"date": "01-11-2026", "merchant": "AMAZON SELLER", "amount": "4,199.00"},
        {"date": "03-11-2026", "merchant": "ZOMATO RESTAURANT", "amount": "710.00"},
        {"date": "05-11-2026", "merchant": "UBER INDIA", "amount": "350.00"},
        {"date": "07-11-2026", "merchant": "SWIGGY INSTAMART", "amount": "890.00"},
        {"date": "08-11-2026", "merchant": "FLIPKART INTERNET", "amount": "3,750.00"},
        {"date": "09-11-2026", "merchant": "IRCTC TOURISM", "amount": "1,450.00"},
        {"date": "10-11-2026", "merchant": "BLINKIT COMMERCE", "amount": "530.00"},
        {"date": "11-11-2026", "merchant": "AMZN PAYMENTS", "amount": "2,100.00"},
        {"date": "12-11-2026", "merchant": "RELIANCE DIGITAL", "amount": "8,990.00"},
        # Secondary user
        {
            "date": "15-10-2026",
            "merchant": "AMZN PAYMENTS",
            "amount": "1,850.00",
            "_user": cfg.secondary_user_id,
        },
        {
            "date": "22-10-2026",
            "merchant": "SWIGGY LIMITED",
            "amount": "620.00",
            "_user": cfg.secondary_user_id,
        },
        {
            "date": "04-11-2026",
            "merchant": "UBER INDIA",
            "amount": "410.00",
            "_user": cfg.secondary_user_id,
        },
    ]

    edge_cases = [
        # Repeated row inside PDF (parser should deduplicate automatically via internal seen_ids)
        {
            "date": "04-09-2026",
            "merchant": "AMZN PAYMENTS",
            "amount": "2,499.00",
            "_edge": "pdf_internal_duplicate",
        },
        # Unmatched garbage text
        {"raw_text": "THIS LINE CONTAINS NO TRANSACTION DATA AT ALL", "_edge": "unmatched_text"},
    ]
    return valid, edge_cases


def get_bank_sms_records(cfg: SyntheticConfig) -> tuple[list[dict], list[dict]]:
    """Return (valid_records, edge_case_records) for Bank SMS."""
    valid = [
        # September 2026
        {
            "message": "Your a/c is credited with Rs. 85,000.00 towards Salary.",
            "timestamp": "2026-09-30T10:00:00Z",
            "reference_id": "SAL20260930",
            "user_id": cfg.user_id,
        },
        {
            "message": "INR 1,250.00 debited from a/c at D-MART.",
            "timestamp": "2026-09-04T17:15:00Z",
            "reference_id": "SMS26090401",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 620.00 spent towards SWIGGY INSTAMART.",
            "timestamp": "2026-09-09T13:40:00Z",
            "reference_id": "SMS26090901",
            "user_id": cfg.user_id,
        },
        {
            "message": "INR 500.00 withdrawn from ATM.",
            "timestamp": "2026-09-13T11:00:00Z",
            "reference_id": "SMS26091301",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 3,450.00 debited towards AMAZON PAYMENTS.",
            "timestamp": "2026-09-19T15:20:00Z",
            "reference_id": "SMS26091901",
            "user_id": cfg.user_id,
        },
        {
            "message": "INR 2,000.00 received from Friend Rahul.",
            "timestamp": "2026-09-22T18:00:00Z",
            "reference_id": "SMS26092201",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 410.00 debited towards UBER TRIP.",
            "timestamp": "2026-09-27T08:30:00Z",
            "reference_id": "SMS26092701",
            "user_id": cfg.user_id,
        },
        # October 2026
        {
            "message": "Your a/c is credited with Rs. 85,000.00 towards Salary.",
            "timestamp": "2026-10-31T10:00:00Z",
            "reference_id": "SAL20261031",
            "user_id": cfg.user_id,
        },
        {
            "message": "INR 840.00 debited from a/c at ZOMATO.",
            "timestamp": "2026-10-03T20:10:00Z",
            "reference_id": "SMS26100301",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 1,890.00 spent at FLIPKART.",
            "timestamp": "2026-10-08T14:00:00Z",
            "reference_id": "SMS26100801",
            "user_id": cfg.user_id,
        },
        {
            "message": "INR 350.00 debited towards OLA CABS.",
            "timestamp": "2026-10-11T09:15:00Z",
            "reference_id": "SMS26101101",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 720.00 debited at BLINKIT.",
            "timestamp": "2026-10-15T16:45:00Z",
            "reference_id": "SMS26101501",
            "user_id": cfg.user_id,
        },
        {
            "message": "INR 4,500.00 received from Client Consulting.",
            "timestamp": "2026-10-18T12:00:00Z",
            "reference_id": "SMS26101801",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 2,150.00 debited towards D-MART.",
            "timestamp": "2026-10-23T19:30:00Z",
            "reference_id": "SMS26102301",
            "user_id": cfg.user_id,
        },
        {
            "message": "INR 580.00 spent at SWIGGY LIMITED.",
            "timestamp": "2026-10-26T21:00:00Z",
            "reference_id": "SMS26102601",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 280.00 debited at METRO.",
            "timestamp": "2026-10-28T08:00:00Z",
            "reference_id": "SMS26102801",
            "user_id": cfg.user_id,
        },
        # November 2026
        {
            "message": "INR 950.00 debited from a/c at SWIGGY.",
            "timestamp": "2026-11-02T13:20:00Z",
            "reference_id": "SMS26110201",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 320.00 spent at UBER INDIA.",
            "timestamp": "2026-11-04T10:10:00Z",
            "reference_id": "SMS26110401",
            "user_id": cfg.user_id,
        },
        {
            "message": "INR 6,200.00 debited towards AMAZON SELLER.",
            "timestamp": "2026-11-06T16:00:00Z",
            "reference_id": "SMS26110601",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 1,100.00 received towards Cashback.",
            "timestamp": "2026-11-08T11:30:00Z",
            "reference_id": "SMS26110801",
            "user_id": cfg.user_id,
        },
        {
            "message": "INR 790.00 debited at ZOMATO.",
            "timestamp": "2026-11-10T20:45:00Z",
            "reference_id": "SMS26111001",
            "user_id": cfg.user_id,
        },
        {
            "message": "Rs. 450.00 spent at BLINKIT.",
            "timestamp": "2026-11-12T15:15:00Z",
            "reference_id": "SMS26111201",
            "user_id": cfg.user_id,
        },
        # Secondary user
        {
            "message": "Your a/c is credited with Rs. 60,000.00 towards Salary.",
            "timestamp": "2026-10-31T11:00:00Z",
            "reference_id": "SAL261031U2",
            "user_id": cfg.secondary_user_id,
        },
        {
            "message": "INR 1,200.00 debited from a/c at AMAZON INDIA.",
            "timestamp": "2026-11-03T14:00:00Z",
            "reference_id": "SMS261103U2",
            "user_id": cfg.secondary_user_id,
        },
        {
            "message": "Rs. 420.00 spent at SWIGGY.",
            "timestamp": "2026-11-09T19:00:00Z",
            "reference_id": "SMS261109U2",
            "user_id": cfg.secondary_user_id,
        },
    ]

    edge_cases = [
        # Missing amount
        {
            "message": "Your account has been debited towards Swiggy with no amount.",
            "timestamp": "2026-09-05T10:00:00Z",
            "user_id": cfg.user_id,
            "_edge": "missing_amount",
        },
        # Ambiguous direction
        {
            "message": "INR 500.00 transaction initiated at Store.",
            "timestamp": "2026-09-06T10:00:00Z",
            "user_id": cfg.user_id,
            "_edge": "unknown_direction",
        },
    ]
    return valid, edge_cases


def get_manual_records(cfg: SyntheticConfig) -> tuple[list[dict], list[dict]]:
    """Return (valid_records, edge_case_records) for Manual Transactions."""
    valid = [
        # September 2026
        {
            "user_id": cfg.user_id,
            "amount": "350.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-09-06T12:00:00Z",
            "merchant_raw": "Local Vegetable Vendor",
            "reference_id": "MAN26090601",
        },
        {
            "user_id": cfg.user_id,
            "amount": "1200.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-09-16T18:30:00Z",
            "merchant_raw": "Pharmacy Store",
            "reference_id": "MAN26091601",
        },
        {
            "user_id": cfg.user_id,
            "amount": "8000.00",
            "currency": "INR",
            "direction": "CREDIT",
            "transaction_timestamp": "2026-09-24T15:00:00Z",
            "merchant_raw": "Freelance Design",
            "reference_id": "MAN26092401",
        },
        {
            "user_id": cfg.user_id,
            "amount": "480.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-09-29T11:15:00Z",
            "merchant_raw": "Coffee House",
            "reference_id": "MAN26092901",
        },
        # October 2026
        {
            "user_id": cfg.user_id,
            "amount": "500.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-10-05T09:30:00Z",
            "merchant_raw": "Auto Rickshaw Cash",
            "reference_id": "MAN26100501",
        },
        {
            "user_id": cfg.user_id,
            "amount": "2500.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-10-12T16:00:00Z",
            "merchant_raw": "Books & Stationery",
            "reference_id": "MAN26101201",
        },
        {
            "user_id": cfg.user_id,
            "amount": "15000.00",
            "currency": "INR",
            "direction": "CREDIT",
            "transaction_timestamp": "2026-10-19T14:00:00Z",
            "merchant_raw": "Consulting Stipend",
            "reference_id": "MAN26101901",
        },
        {
            "user_id": cfg.user_id,
            "amount": "650.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-10-24T13:45:00Z",
            "merchant_raw": "Lunch with Team",
            "reference_id": "MAN26102401",
        },
        {
            "user_id": cfg.user_id,
            "amount": "1800.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-10-27T17:10:00Z",
            "merchant_raw": "Hardware Tools",
            "reference_id": "MAN26102701",
        },
        {
            "user_id": cfg.user_id,
            "amount": "320.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-10-30T19:20:00Z",
            "merchant_raw": "Snack Corner",
            "reference_id": "MAN26103001",
        },
        # November 2026
        {
            "user_id": cfg.user_id,
            "amount": "400.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-11-03T10:00:00Z",
            "merchant_raw": "Local Laundry",
            "reference_id": "MAN26110301",
        },
        {
            "user_id": cfg.user_id,
            "amount": "3100.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-11-07T15:30:00Z",
            "merchant_raw": "Home Maintenance",
            "reference_id": "MAN26110701",
        },
        {
            "user_id": cfg.user_id,
            "amount": "5000.00",
            "currency": "INR",
            "direction": "CREDIT",
            "transaction_timestamp": "2026-11-09T11:00:00Z",
            "merchant_raw": "Tutoring Income",
            "reference_id": "MAN26110901",
        },
        {
            "user_id": cfg.user_id,
            "amount": "750.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-11-11T14:40:00Z",
            "merchant_raw": "Pet Store Supplies",
            "reference_id": "MAN26111101",
        },
        {
            "user_id": cfg.user_id,
            "amount": "1100.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-11-12T18:00:00Z",
            "merchant_raw": "Dry Cleaning",
            "reference_id": "MAN26111201",
        },
        {
            "user_id": cfg.user_id,
            "amount": "250.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-11-13T12:15:00Z",
            "merchant_raw": "Newspaper Subscription",
            "reference_id": "MAN26111301",
        },
        # Secondary user
        {
            "user_id": cfg.secondary_user_id,
            "amount": "700.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-10-10T12:00:00Z",
            "merchant_raw": "Bookstore",
            "reference_id": "MAN261010U2",
        },
        {
            "user_id": cfg.secondary_user_id,
            "amount": "10000.00",
            "currency": "INR",
            "direction": "CREDIT",
            "transaction_timestamp": "2026-10-25T15:00:00Z",
            "merchant_raw": "Bonus Prize",
            "reference_id": "MAN261025U2",
        },
        {
            "user_id": cfg.secondary_user_id,
            "amount": "550.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-11-02T16:00:00Z",
            "merchant_raw": "Cafe",
            "reference_id": "MAN261102U2",
        },
        {
            "user_id": cfg.secondary_user_id,
            "amount": "1350.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-11-08T11:00:00Z",
            "merchant_raw": "Grocery Store",
            "reference_id": "MAN261108U2",
        },
    ]

    edge_cases = [
        # Negative amount
        {
            "user_id": cfg.user_id,
            "amount": "-500.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "2026-09-10T10:00:00Z",
            "merchant_raw": "Negative Merchant",
            "reference_id": "MAN_FAIL_1",
            "_edge": "negative_amount",
        },
        # Missing direction
        {
            "user_id": cfg.user_id,
            "amount": "500.00",
            "currency": "INR",
            "direction": "",
            "transaction_timestamp": "2026-09-11T10:00:00Z",
            "merchant_raw": "No Direction",
            "reference_id": "MAN_FAIL_2",
            "_edge": "missing_direction",
        },
        # Invalid timestamp
        {
            "user_id": cfg.user_id,
            "amount": "500.00",
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": "INVALID_TIMESTAMP",
            "merchant_raw": "Bad Date",
            "reference_id": "MAN_FAIL_3",
            "_edge": "invalid_timestamp",
        },
    ]
    return valid, edge_cases


def generate_all_synthetic_files(cfg: SyntheticConfig | None = None) -> dict:
    """Generate all synthetic files and return manifest with expected totals."""
    cfg = cfg or SyntheticConfig()
    base_dir = cfg.output_dir
    raw_dir = base_dir / "raw"

    raw_upi_dir = raw_dir / "upi"
    raw_card_dir = raw_dir / "card"
    raw_sms_dir = raw_dir / "bank_sms"
    raw_manual_dir = raw_dir / "manual"

    for d in [raw_upi_dir, raw_card_dir, raw_sms_dir, raw_manual_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 1. Generate UPI CSV
    upi_valid, upi_edge = get_upi_records(cfg)
    upi_csv_path = raw_upi_dir / "upi_transactions.csv"
    with upi_csv_path.open("w", encoding="utf-8") as f:
        f.write("date,amount,type,merchant,reference_id,currency\n")
        for r in upi_valid:
            f.write(
                f"{r['date']},{r['amount']},{r['type']},{r['merchant']},{r['reference_id']},{r['currency']}\n"
            )

    # Also generate invalid UPI CSV for edge case testing
    upi_invalid_path = raw_upi_dir / "upi_edge_cases.csv"
    with upi_invalid_path.open("w", encoding="utf-8") as f:
        f.write("date,amount,type,merchant,reference_id,currency\n")
        for r in upi_edge:
            f.write(
                f"{r['date']},{r['amount']},{r['type']},{r['merchant']},{r['reference_id']},{r['currency']}\n"
            )

    # 2. Generate Card PDF
    card_valid, card_edge = get_card_pdf_records(cfg)
    card_pdf_path = raw_card_dir / "card_statement.pdf"
    doc = fitz.open()
    page = doc.new_page()

    lines = ["FINPULSE SYNTHETIC CREDIT CARD STATEMENT", "========================================"]
    for r in card_valid:
        lines.append(f"{r['date']}  {r['merchant']}  {r['amount']}")
    # Add the edge case lines (including the duplicate and noise)
    lines.append(f"{card_edge[0]['date']}  {card_edge[0]['merchant']}  {card_edge[0]['amount']}")
    lines.append(card_edge[1]["raw_text"])

    text_content = "\n".join(lines)
    # PyMuPDF insert_textbox
    rect = fitz.Rect(50, 50, 550, 800)
    page.insert_textbox(rect, text_content, fontsize=9, fontname="Courier")
    doc.save(str(card_pdf_path))
    doc.close()

    # 3. Generate Bank SMS JSON
    sms_valid, sms_edge = get_bank_sms_records(cfg)
    sms_json_path = raw_sms_dir / "bank_sms.json"
    with sms_json_path.open("w", encoding="utf-8") as f:
        json.dump(sms_valid, f, indent=2)

    sms_edge_path = raw_sms_dir / "bank_sms_edge_cases.json"
    with sms_edge_path.open("w", encoding="utf-8") as f:
        json.dump(sms_edge, f, indent=2)

    # 4. Generate Manual Transactions JSON
    man_valid, man_edge = get_manual_records(cfg)
    manual_json_path = raw_manual_dir / "manual_transactions.json"
    with manual_json_path.open("w", encoding="utf-8") as f:
        json.dump(man_valid, f, indent=2)

    manual_edge_path = raw_manual_dir / "manual_edge_cases.json"
    with manual_edge_path.open("w", encoding="utf-8") as f:
        json.dump(man_edge, f, indent=2)

    manifest = {
        "generator": "FinPulse Synthetic Data Generator",
        "seed": cfg.seed,
        "primary_user": cfg.user_id,
        "secondary_user": cfg.secondary_user_id,
        "files": {
            "upi_csv": str(upi_csv_path),
            "upi_edge_cases_csv": str(upi_invalid_path),
            "card_pdf": str(card_pdf_path),
            "bank_sms_json": str(sms_json_path),
            "bank_sms_edge_cases_json": str(sms_edge_path),
            "manual_json": str(manual_json_path),
            "manual_edge_cases_json": str(manual_edge_path),
        },
        "counts": {
            "upi_valid": len(upi_valid),
            "upi_edge": len(upi_edge),
            "card_valid": len(card_valid),
            "card_edge": len(card_edge),
            "sms_valid": len(sms_valid),
            "sms_edge": len(sms_edge),
            "manual_valid": len(man_valid),
            "manual_edge": len(man_edge),
            "total_valid": len(upi_valid) + len(card_valid) + len(sms_valid) + len(man_valid),
            "total_edge": len(upi_edge) + len(card_edge) + len(sms_edge) + len(man_edge),
        },
    }

    manifest_path = base_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(
        "Generated synthetic data with %d valid records across 4 sources.",
        manifest["counts"]["total_valid"],
    )
    return manifest


if __name__ == "__main__":
    generate_all_synthetic_files()
