from datetime import date
from decimal import Decimal

import pytest

from dashboard.queries import (
    get_cashflow_summary,
    get_category_spending,
    get_daily_spending_trend,
    get_data_freshness,
    get_filter_bounds,
    get_filtered_transactions,
    get_merchant_spending,
    get_monthly_spending_trend,
    get_overview_kpis,
)


def test_get_filter_bounds(populated_duckdb):
    bounds = get_filter_bounds(populated_duckdb)
    assert bounds["min_date"] == date(2026, 11, 10)
    assert bounds["max_date"] == date(2026, 11, 11)
    assert "user_1" in bounds["users"]
    assert "INR" in bounds["currencies"]


def test_get_overview_kpis(populated_duckdb):
    kpis = get_overview_kpis(currency="INR", db_path=populated_duckdb)
    # Total income: 50,000. Total expenses: 500 + 1500 + 250 = 2250
    assert kpis["total_income"] == Decimal("50000.00")
    assert kpis["total_expenses"] == Decimal("2250.00")
    assert kpis["net_cash_flow"] == Decimal("47750.00")
    assert kpis["total_transactions"] == 4
    assert kpis["savings_rate_pct"] == pytest.approx(95.5, 0.01)
    # Average ticket: 2250 / 3 debit transactions = 750.0
    assert kpis["avg_transaction_value"] == pytest.approx(750.0, 0.01)


def test_get_daily_spending_trend(populated_duckdb):
    df = get_daily_spending_trend(currency="INR", db_path=populated_duckdb)
    assert len(df) == 2
    assert df.iloc[0]["expenses"] == Decimal("2000.00")
    assert df.iloc[1]["expenses"] == Decimal("250.00")


def test_get_monthly_spending_trend(populated_duckdb):
    df = get_monthly_spending_trend(currency="INR", db_path=populated_duckdb)
    assert len(df) == 1
    assert df.iloc[0]["expenses"] == Decimal("2250.00")
    assert df.iloc[0]["income"] == Decimal("50000.00")


def test_get_category_spending(populated_duckdb):
    df = get_category_spending(currency="INR", db_path=populated_duckdb)
    cat_dict = dict(zip(df["spending_category"], df["total_spent"]))
    assert cat_dict["Shopping"] == Decimal("1500.00")
    assert cat_dict["Food & Groceries"] == Decimal("500.00")
    assert cat_dict["Travel & Commute"] == Decimal("250.00")


def test_get_merchant_spending(populated_duckdb):
    df = get_merchant_spending(currency="INR", limit=5, db_path=populated_duckdb)
    merch_dict = dict(zip(df["merchant_name"], df["total_spent"]))
    assert merch_dict["Amazon"] == Decimal("1500.00")
    assert merch_dict["Swiggy"] == Decimal("500.00")
    assert merch_dict["Uber"] == Decimal("250.00")


def test_get_cashflow_summary(populated_duckdb):
    df = get_cashflow_summary(currency="INR", db_path=populated_duckdb)
    cf_dict = dict(zip(df["direction"], df["total_volume"]))
    assert cf_dict["DEBIT"] == Decimal("2250.00")
    assert cf_dict["CREDIT"] == Decimal("50000.00")


def test_get_filtered_transactions(populated_duckdb):
    df, total = get_filtered_transactions(
        direction="DEBIT",
        merchant_search="Amazon",
        currency="INR",
        db_path=populated_duckdb,
    )
    assert total == 1
    assert len(df) == 1
    assert df.iloc[0]["merchant_name"] == "Amazon"


def test_get_data_freshness(populated_duckdb):
    freshness = get_data_freshness(populated_duckdb)
    assert freshness["total_rows"] == 4
    assert freshness["latest_processed_at"] is not None
