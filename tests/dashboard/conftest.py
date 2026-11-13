import duckdb
import pytest


@pytest.fixture
def populated_duckdb(tmp_path):
    db_file = tmp_path / "finpulse_test.duckdb"

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
            INSERT INTO silver.transactions VALUES
            ('t1', 'user_1', 500.00, 'INR', 'DEBIT', '2026-11-10 10:00:00+00',
             'SWIGGY', 'Swiggy', 'R1', 'UPI_CSV', 'k1', '2026-11-10 10:05:00+00', '1.0'),
            ('t2', 'user_1', 1500.00, 'INR', 'DEBIT', '2026-11-10 12:00:00+00',
             'AMAZON', 'Amazon', 'R2', 'UPI_CSV', 'k2', '2026-11-10 12:05:00+00', '1.0'),
            ('t3', 'user_1', 50000.00, 'INR', 'CREDIT', '2026-11-10 14:00:00+00',
             'SALARY', 'Salary', 'R3', 'UPI_CSV', 'k3', '2026-11-10 14:05:00+00', '1.0'),
            ('t4', 'user_1', 250.00, 'INR', 'DEBIT', '2026-11-11 09:00:00+00',
             'UBER', 'Uber', 'R4', 'UPI_CSV', 'k4', '2026-11-11 09:05:00+00', '1.0')
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
            CREATE TABLE main.gold_daily_spending AS
            SELECT
                user_id,
                transaction_date,
                currency,
                coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0)
                    as total_debit_amount,
                coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0)
                    as total_credit_amount,
                coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0)
                    - coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0)
                    as net_cash_flow,
                coalesce(sum(case when direction = 'DEBIT' then 1 else 0 end), 0) as debit_count,
                coalesce(sum(case when direction = 'CREDIT' then 1 else 0 end), 0) as credit_count,
                count(*) as total_transactions
            FROM main.stg_transactions
            GROUP BY 1, 2, 3
            """
        )

        con.execute(
            """
            CREATE TABLE main.gold_monthly_spending AS
            SELECT
                user_id,
                transaction_month,
                currency,
                coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0)
                    as monthly_expenses,
                coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0)
                    as monthly_income,
                coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0)
                    - coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0)
                    as net_savings,
                round((coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0)
                    - coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0))
                    / sum(case when direction = 'CREDIT' then amount else 0 end) * 100, 2)
                    as savings_rate_pct,
                count(*) as total_transactions
            FROM main.stg_transactions
            GROUP BY 1, 2, 3
            """
        )

        con.execute(
            """
            CREATE TABLE main.gold_merchant_spending AS
            SELECT
                user_id,
                merchant_name,
                currency,
                sum(amount) as total_spent,
                count(*) as transaction_count,
                round(avg(amount), 2) as avg_ticket_size,
                min(transaction_date) as first_purchase_date,
                max(transaction_date) as last_purchase_date
            FROM main.stg_transactions
            WHERE direction = 'DEBIT'
            GROUP BY 1, 2, 3
            """
        )

        con.execute(
            """
            CREATE TABLE main.gold_category_spending AS
            SELECT
                user_id,
                case
                    when lower(merchant_name) like '%amazon%' then 'Shopping'
                    when lower(merchant_name) like '%swiggy%' then 'Food & Groceries'
                    when lower(merchant_name) like '%uber%' then 'Travel & Commute'
                    else 'Uncategorized'
                end as spending_category,
                currency,
                sum(amount) as total_spent,
                count(*) as transaction_count,
                round(avg(amount), 2) as avg_amount
            FROM main.stg_transactions
            WHERE direction = 'DEBIT'
            GROUP BY 1, 2, 3
            """
        )

        con.execute(
            """
            CREATE TABLE main.gold_cashflow_summary AS
            SELECT
                user_id,
                direction,
                currency,
                sum(amount) as total_volume,
                count(*) as transaction_count,
                round(avg(amount), 2) as avg_amount,
                min(amount) as min_amount,
                max(amount) as max_amount
            FROM main.stg_transactions
            GROUP BY 1, 2, 3
            """
        )

    return db_file
