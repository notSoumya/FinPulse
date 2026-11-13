from datetime import date
from decimal import Decimal

from dashboard.queries import get_filtered_transactions, get_overview_kpis


def test_date_filter_narrows_kpis(populated_duckdb):
    # Only Day 1 (Nov 10)
    kpis_day1 = get_overview_kpis(
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 10),
        currency="INR",
        db_path=populated_duckdb,
    )
    assert kpis_day1["total_expenses"] == Decimal("2000.00")
    assert kpis_day1["total_transactions"] == 3

    # Only Day 2 (Nov 11)
    kpis_day2 = get_overview_kpis(
        start_date=date(2026, 11, 11),
        end_date=date(2026, 11, 11),
        currency="INR",
        db_path=populated_duckdb,
    )
    assert kpis_day2["total_expenses"] == Decimal("250.00")
    assert kpis_day2["total_transactions"] == 1


def test_user_filter(populated_duckdb):
    kpis_user1 = get_overview_kpis(
        user_id="user_1",
        currency="INR",
        db_path=populated_duckdb,
    )
    assert kpis_user1["total_transactions"] == 4

    kpis_missing = get_overview_kpis(
        user_id="user_999",
        currency="INR",
        db_path=populated_duckdb,
    )
    assert kpis_missing["total_transactions"] == 0


def test_transaction_search_case_insensitive(populated_duckdb):
    df_lower, count_lower = get_filtered_transactions(
        merchant_search="swiggy",
        currency="INR",
        db_path=populated_duckdb,
    )
    df_upper, count_upper = get_filtered_transactions(
        merchant_search="SWIGGY",
        currency="INR",
        db_path=populated_duckdb,
    )
    assert count_lower == 1
    assert count_upper == 1
    assert df_lower.iloc[0]["transaction_id"] == "t1"
    assert df_upper.iloc[0]["transaction_id"] == "t1"


def test_transaction_direction_filter(populated_duckdb):
    df_debits, total_debits = get_filtered_transactions(
        direction="DEBIT",
        currency="INR",
        db_path=populated_duckdb,
    )
    df_credits, total_credits = get_filtered_transactions(
        direction="CREDIT",
        currency="INR",
        db_path=populated_duckdb,
    )
    assert total_debits == 3
    assert total_credits == 1
