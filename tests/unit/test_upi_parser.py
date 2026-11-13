from decimal import Decimal

import pytest

from finpulse.ingestion.parsers.upi_parser import parse_upi_csv


def test_upi_csv_parser(tmp_path):

    csv_file = tmp_path / "sample.csv"

    csv_file.write_text(
        "date,amount,type,merchant,reference_id,currency\n"
        "2026-11-07 12:30:00,500.00,DR,Amazon,UPI123,INR\n"
        "2026-11-07 14:00:00,1200.00,CR,Salary,UPI124,INR\n",
        encoding="utf-8",
    )

    transactions = parse_upi_csv(str(csv_file), "user_001")

    assert len(transactions) == 2
    assert transactions[0].amount == Decimal("500.00")
    assert transactions[0].direction == "DEBIT"
    assert transactions[1].direction == "CREDIT"
    assert transactions[0].source_type == "UPI_CSV"


def test_upi_parser_rejects_missing_columns(tmp_path):

    csv_file = tmp_path / "invalid.csv"

    csv_file.write_text(
        "date,amount\n2026-11-07,500\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Missing required columns"):
        parse_upi_csv(str(csv_file), "user_001")


def test_upi_parser_rejects_invalid_direction(tmp_path):

    csv_file = tmp_path / "invalid_direction.csv"

    csv_file.write_text(
        "date,amount,type,merchant\n2026-11-07,500,UNKNOWN,Amazon\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid transaction type"):
        parse_upi_csv(str(csv_file), "user_001")
