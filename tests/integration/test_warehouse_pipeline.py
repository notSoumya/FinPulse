import os
from datetime import UTC, datetime
from decimal import Decimal

import duckdb
import pyarrow as pa
import pytest
from deltalake import write_deltalake

from finpulse.warehouse.pipeline import run_warehouse_pipeline


@pytest.fixture
def rich_silver_transactions():
    data = [
        # User 1: Day 1
        {
            "transaction_id": "txn_001",
            "user_id": "user_1",
            "amount": Decimal("500.00"),
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 11, 10, 10, 0, tzinfo=UTC),
            "merchant_raw": "SWIGGY",
            "merchant_normalized": "Swiggy",
            "reference_id": "REF1",
            "source_type": "UPI_CSV",
            "deduplication_key": "k1",
            "processed_at": datetime(2026, 11, 10, 10, 5, tzinfo=UTC),
            "schema_version": "1.0",
        },
        {
            "transaction_id": "txn_002",
            "user_id": "user_1",
            "amount": Decimal("1500.00"),
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 11, 10, 14, 0, tzinfo=UTC),
            "merchant_raw": "AMAZON PAY",
            "merchant_normalized": "Amazon",
            "reference_id": "REF2",
            "source_type": "UPI_CSV",
            "deduplication_key": "k2",
            "processed_at": datetime(2026, 11, 10, 14, 5, tzinfo=UTC),
            "schema_version": "1.0",
        },
        # User 1: Day 1 Income
        {
            "transaction_id": "txn_003",
            "user_id": "user_1",
            "amount": Decimal("50000.00"),
            "currency": "INR",
            "direction": "CREDIT",
            "transaction_timestamp": datetime(2026, 11, 10, 9, 0, tzinfo=UTC),
            "merchant_raw": "COMPANY SALARY",
            "merchant_normalized": "Company Salary",
            "reference_id": "REF3",
            "source_type": "BANK_SMS",
            "deduplication_key": "k3",
            "processed_at": datetime(2026, 11, 10, 9, 5, tzinfo=UTC),
            "schema_version": "1.0",
        },
        # User 1: Day 2
        {
            "transaction_id": "txn_004",
            "user_id": "user_1",
            "amount": Decimal("250.00"),
            "currency": "INR",
            "direction": "DEBIT",
            "transaction_timestamp": datetime(2026, 11, 11, 8, 30, tzinfo=UTC),
            "merchant_raw": "UBER INDIA",
            "merchant_normalized": "Uber",
            "reference_id": "REF4",
            "source_type": "CARD_PDF",
            "deduplication_key": "k4",
            "processed_at": datetime(2026, 11, 11, 8, 35, tzinfo=UTC),
            "schema_version": "1.0",
        },
    ]
    return pa.Table.from_pylist(data)


def test_end_to_end_warehouse_pipeline(tmp_path, rich_silver_transactions):
    silver_path = tmp_path / "silver"
    db_path = tmp_path / "warehouse" / "finpulse.duckdb"

    # 1. Create upstream Silver Delta table
    write_deltalake(str(silver_path), rich_silver_transactions, mode="error")

    # Set FINPULSE_DUCKDB_PATH for dbt profile
    os.environ["FINPULSE_DUCKDB_PATH"] = str(db_path).replace("\\", "/")

    try:
        # 2. Run warehouse pipeline
        res = run_warehouse_pipeline(
            silver_path=str(silver_path),
            db_path=str(db_path),
            project_dir="dbt",
            profiles_dir="dbt",
        )

        assert res["success"] is True
        assert res["rows_synced"] == 4
        assert res["dbt_models_run"] == 7
        assert res["dbt_tests_run"] == 27

        # 3. Verify analytics in Gold Marts
        with duckdb.connect(str(db_path)) as con:
            # Daily spending check
            daily_rows = con.execute(
                "SELECT transaction_date, total_debit_amount, "
                "total_credit_amount, net_cash_flow "
                "FROM main.gold_daily_spending ORDER BY transaction_date"
            ).fetchall()
            assert len(daily_rows) == 2
            # Day 1: 500 + 1500 = 2000 debit, 50000 credit, net +48000
            assert daily_rows[0][1] == Decimal("2000.00")
            assert daily_rows[0][2] == Decimal("50000.00")
            assert daily_rows[0][3] == Decimal("48000.00")
            # Day 2: 250 debit, 0 credit, net -250
            assert daily_rows[1][1] == Decimal("250.00")
            assert daily_rows[1][2] == Decimal("0.00")
            assert daily_rows[1][3] == Decimal("-250.00")

            # Monthly spending check
            monthly_row = con.execute(
                "SELECT monthly_expenses, monthly_income, "
                "net_savings, savings_rate_pct FROM main.gold_monthly_spending"
            ).fetchone()
            assert monthly_row[0] == Decimal("2250.00")
            assert monthly_row[1] == Decimal("50000.00")
            assert monthly_row[2] == Decimal("47750.00")
            assert float(monthly_row[3]) == pytest.approx(95.5, 0.01)

            # Merchant spending check
            merchants = dict(
                con.execute(
                    "SELECT merchant_name, total_spent FROM main.gold_merchant_spending"
                ).fetchall()
            )
            assert merchants["Amazon"] == Decimal("1500.00")
            assert merchants["Swiggy"] == Decimal("500.00")
            assert merchants["Uber"] == Decimal("250.00")

            # Cashflow summary check
            cashflows = dict(
                con.execute(
                    "SELECT direction, total_volume FROM main.gold_cashflow_summary"
                ).fetchall()
            )
            assert cashflows["DEBIT"] == Decimal("2250.00")
            assert cashflows["CREDIT"] == Decimal("50000.00")

            # Category spending check
            categories = dict(
                con.execute(
                    "SELECT spending_category, total_spent FROM main.gold_category_spending"
                ).fetchall()
            )
            assert categories["Shopping"] == Decimal("1500.00")
            assert categories["Food & Groceries"] == Decimal("500.00")
            assert categories["Travel & Commute"] == Decimal("250.00")

    finally:
        os.environ.pop("FINPULSE_DUCKDB_PATH", None)
