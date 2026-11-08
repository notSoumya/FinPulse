
import re
from datetime import UTC, datetime
from decimal import Decimal

import pdfplumber

from finpulse.common.hashing import generate_transaction_id
from finpulse.common.models import Transaction

TRANSACTION_PATTERN = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+(.+?)\s+([0-9,]+\.\d{2})"
)


def extract_pdf_text(file_path: str) -> str:
    """Extract selectable text from every page of a PDF."""
    pages = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")

    text = "\n".join(pages)

    if not text.strip():
        raise ValueError(
            "No selectable text found. PDF may require OCR."
        )

    return text


def parse_card_pdf(
    file_path: str,
    user_id: str,
) -> list[Transaction]:
    """Parse credit-card transactions from a supported PDF format."""

    text = extract_pdf_text(file_path)

    transactions = []
    seen_ids = set()

    for line in text.splitlines():
        match = TRANSACTION_PATTERN.search(line)

        if not match:
            continue

        date_str, merchant, amount_str = match.groups()

        timestamp = datetime.strptime(
            date_str, "%d-%m-%Y"
        ).replace(tzinfo=UTC)

        amount = Decimal(amount_str.replace(",", ""))
        merchant = merchant.strip()

        direction = "DEBIT"

        transaction_id = generate_transaction_id(
            user_id=user_id,
            source_type="CARD_PDF",
            amount=amount,
            timestamp=timestamp,
            direction=direction,
            merchant=merchant,
        )

        # Skip duplicate records extracted from the PDF.
        if transaction_id in seen_ids:
            continue

        seen_ids.add(transaction_id)

        transaction = Transaction(
            transaction_id=transaction_id,
            user_id=user_id,
            amount=amount,
            currency="INR",
            direction=direction,
            transaction_timestamp=timestamp,
            merchant_raw=merchant,
            merchant_normalized=None,
            reference_id=None,
            source_type="CARD_PDF",
        )

        transactions.append(transaction)

    return transactions