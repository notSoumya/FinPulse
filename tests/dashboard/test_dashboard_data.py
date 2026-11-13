from decimal import Decimal

import duckdb
import pytest

from dashboard.database import get_db_connection
from dashboard.queries import (
    get_cashflow_summary,
    get_category_spending,
    get_daily_spending_trend,
    get_filtered_transactions,
    get_merchant_spending,
    get_monthly_spending_trend,
    get_overview_kpis,
)


@pytest.fixture
def empty_duckdb(tmp_path):
    db_file = tmp_path / "empty_finpulse.duckdb"

    with duckdb.connect(str(db_file)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS silver")
        con.execute(
            """
            CREATE TABLE silver.transactions (
                transaction_id VARCHAR,
                user_id VARCHAR,
                amount DECIMAL(18, 2),
                currency VARCHAR,
                direction VARCHAR,
                transaction_timestamp TIMESTAMPTZ,
                merchant_raw VARCHAR,
                merchant_normalized VARCHAR,
                reference_id VARCHAR,
                source_type VARCHAR,
                deduplication_key VARCHAR,
                processed_at TIMESTAMPTZ,
                schema_version VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE VIEW main.stg_transactions AS
            SELECT
                transaction_id,
                user_id,
                amount,
                currency,
                direction,
                transaction_timestamp,
                CAST(transaction_timestamp AS DATE) as transaction_date,
                date_trunc('month', transaction_timestamp) as transaction_month,
                coalesce(merchant_normalized, merchant_raw, 'Unknown') as merchant_name,
                reference_id,
                source_type
            FROM silver.transactions
            """
        )
        con.execute(
            """
            CREATE TABLE main.gold_daily_spending (
                user_id VARCHAR,
                transaction_date DATE,
                currency VARCHAR,
                total_debit_amount DECIMAL(18, 2),
                total_credit_amount DECIMAL(18, 2),
                net_cash_flow DECIMAL(18, 2),
                debit_count BIGINT,
                credit_count BIGINT,
                total_transactions BIGINT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE main.gold_monthly_spending (
                user_id VARCHAR,
                transaction_month DATE,
                currency VARCHAR,
                monthly_expenses DECIMAL(18, 2),
                monthly_income DECIMAL(18, 2),
                net_savings DECIMAL(18, 2),
                savings_rate_pct DOUBLE,
                total_transactions BIGINT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE main.gold_merchant_spending (
                user_id VARCHAR,
                merchant_name VARCHAR,
                currency VARCHAR,
                total_spent DECIMAL(18, 2),
                transaction_count BIGINT,
                avg_ticket_size DECIMAL(18, 2),
                first_purchase_date DATE,
                last_purchase_date DATE
            )
            """
        )
        con.execute(
            """
            CREATE TABLE main.gold_category_spending (
                user_id VARCHAR,
                spending_category VARCHAR,
                currency VARCHAR,
                total_spent DECIMAL(18, 2),
                transaction_count BIGINT,
                avg_amount DECIMAL(18, 2)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE main.gold_cashflow_summary (
                user_id VARCHAR,
                direction VARCHAR,
                currency VARCHAR,
                total_volume DECIMAL(18, 2),
                transaction_count BIGINT,
                avg_amount DECIMAL(18, 2),
                min_amount DECIMAL(18, 2),
                max_amount DECIMAL(18, 2)
            )
            """
        )

    return db_file


def test_empty_database_kpis(empty_duckdb):
    kpis = get_overview_kpis(db_path=empty_duckdb)
    assert kpis["total_income"] == Decimal("0.00")
    assert kpis["total_expenses"] == Decimal("0.00")
    assert kpis["net_cash_flow"] == Decimal("0.00")
    assert kpis["total_transactions"] == 0
    assert kpis["savings_rate_pct"] is None
    assert kpis["avg_transaction_value"] is None


def test_empty_database_dataframes(empty_duckdb):
    assert get_daily_spending_trend(db_path=empty_duckdb).empty
    assert get_monthly_spending_trend(db_path=empty_duckdb).empty
    assert get_category_spending(db_path=empty_duckdb).empty
    assert get_merchant_spending(db_path=empty_duckdb).empty
    assert get_cashflow_summary(db_path=empty_duckdb).empty

    df_txns, total = get_filtered_transactions(db_path=empty_duckdb)
    assert df_txns.empty
    assert total == 0


def test_concurrent_read_connections(empty_duckdb):
    # Multiple read-only connections should not block or lock each other
    with get_db_connection(empty_duckdb) as con1:
        res1 = con1.execute("SELECT count(*) FROM silver.transactions").fetchone()[0]
        with get_db_connection(empty_duckdb) as con2:
            res2 = con2.execute("SELECT count(*) FROM silver.transactions").fetchone()[0]
            assert res1 == 0
            assert res2 == 0
