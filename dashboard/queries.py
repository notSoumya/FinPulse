import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from dashboard.database import DatabaseUnavailableError, get_db_connection
from dashboard.metrics import calculate_avg_ticket, calculate_savings_rate

logger = logging.getLogger(__name__)


def get_filter_bounds(db_path: Path | None = None) -> dict[str, Any]:
    """Retrieve available date ranges, users, and currencies from the warehouse."""
    try:
        with get_db_connection(db_path) as con:
            res = con.execute(
                """
                SELECT
                    min(transaction_date) as min_date,
                    max(transaction_date) as max_date,
                    count(DISTINCT user_id) as user_count,
                    array_agg(DISTINCT user_id) as users,
                    array_agg(DISTINCT currency) as currencies
                FROM main.gold_daily_spending
                """
            ).fetchone()

            if not res or res[0] is None:
                return {
                    "min_date": date.today(),
                    "max_date": date.today(),
                    "users": [],
                    "currencies": ["INR"],
                }

            return {
                "min_date": res[0],
                "max_date": res[1],
                "users": [u for u in (res[3] or []) if u],
                "currencies": [c for c in (res[4] or []) if c],
            }
    except (DatabaseUnavailableError, Exception) as exc:
        logger.warning("Could not fetch filter bounds: %s", exc)
        return {
            "min_date": date.today(),
            "max_date": date.today(),
            "users": [],
            "currencies": ["INR"],
        }


def get_overview_kpis(
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Fetch high-level KPI metrics for the selected time range and filters."""
    query = """
        SELECT
            coalesce(sum(total_credit_amount), 0) as total_income,
            coalesce(sum(total_debit_amount), 0) as total_expenses,
            coalesce(sum(net_cash_flow), 0) as net_cash_flow,
            coalesce(sum(debit_count), 0) as debit_count,
            coalesce(sum(credit_count), 0) as credit_count,
            coalesce(sum(total_transactions), 0) as total_transactions,
            max(transaction_date) as latest_date
        FROM main.gold_daily_spending
        WHERE currency = ?
    """
    params: list[Any] = [currency]

    if start_date:
        query += " AND transaction_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND transaction_date <= ?"
        params.append(end_date)
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    with get_db_connection(db_path) as con:
        row = con.execute(query, params).fetchone()

    if not row or row[5] == 0:
        return {
            "total_income": Decimal("0.00"),
            "total_expenses": Decimal("0.00"),
            "net_cash_flow": Decimal("0.00"),
            "savings_rate_pct": None,
            "total_transactions": 0,
            "avg_transaction_value": None,
            "latest_transaction_date": None,
        }

    income = row[0]
    expenses = row[1]
    net_cf = row[2]
    debit_count = int(row[3])
    total_txns = int(row[5])
    latest_date = row[6]

    savings_rate = calculate_savings_rate(income, expenses)
    avg_ticket = calculate_avg_ticket(expenses, debit_count)

    return {
        "total_income": income,
        "total_expenses": expenses,
        "net_cash_flow": net_cf,
        "savings_rate_pct": savings_rate,
        "total_transactions": total_txns,
        "avg_transaction_value": avg_ticket,
        "latest_transaction_date": latest_date,
    }


def get_daily_spending_trend(
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch daily time series for debit, credit, and net cash flow."""
    query = """
        SELECT
            transaction_date,
            total_debit_amount as expenses,
            total_credit_amount as income,
            net_cash_flow,
            total_transactions
        FROM main.gold_daily_spending
        WHERE currency = ?
    """
    params: list[Any] = [currency]

    if start_date:
        query += " AND transaction_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND transaction_date <= ?"
        params.append(end_date)
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    query += " ORDER BY transaction_date ASC"

    with get_db_connection(db_path) as con:
        return con.execute(query, params).df()


def get_monthly_spending_trend(
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch monthly aggregated metrics from gold_monthly_spending."""
    query = """
        SELECT
            transaction_month,
            monthly_expenses as expenses,
            monthly_income as income,
            net_savings,
            savings_rate_pct,
            total_transactions
        FROM main.gold_monthly_spending
        WHERE currency = ?
    """
    params: list[Any] = [currency]
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    query += " ORDER BY transaction_month ASC"

    with get_db_connection(db_path) as con:
        return con.execute(query, params).df()


def get_category_spending(
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch category-wise expenditure summary from gold_category_spending or stg_transactions."""
    # When filtering by date, derive categories dynamically from stg_transactions
    if start_date or end_date:
        query = """
            SELECT
                case
                    when lower(merchant_name) like '%amazon%'
                        or lower(merchant_name) like '%flipkart%' then 'Shopping'
                    when lower(merchant_name) like '%swiggy%'
                        or lower(merchant_name) like '%zomato%'
                        or lower(merchant_name) like '%blinkit%'
                        or lower(merchant_name) like '%instamart%' then 'Food & Groceries'
                    when lower(merchant_name) like '%uber%'
                        or lower(merchant_name) like '%ola%'
                        or lower(merchant_name) like '%metro%'
                        or lower(merchant_name) like '%irctc%' then 'Travel & Commute'
                    when lower(merchant_name) like '%salary%' then 'Income'
                    else 'Uncategorized'
                end as spending_category,
                sum(amount) as total_spent,
                count(*) as transaction_count,
                round(avg(amount), 2) as avg_amount
            FROM main.stg_transactions
            WHERE direction = 'DEBIT' AND currency = ?
        """
        params: list[Any] = [currency]
        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " GROUP BY 1 ORDER BY total_spent DESC"
    else:
        query = """
            SELECT
                spending_category,
                sum(total_spent) as total_spent,
                sum(transaction_count) as transaction_count,
                round(avg(avg_amount), 2) as avg_amount
            FROM main.gold_category_spending
            WHERE currency = ?
        """
        params = [currency]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " GROUP BY spending_category ORDER BY total_spent DESC"

    with get_db_connection(db_path) as con:
        return con.execute(query, params).df()


def get_merchant_spending(
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    currency: str = "INR",
    limit: int = 10,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch top merchants by spending from gold_merchant_spending or stg_transactions."""
    if start_date or end_date:
        query = """
            SELECT
                merchant_name,
                sum(amount) as total_spent,
                count(*) as transaction_count,
                round(avg(amount), 2) as avg_ticket_size,
                min(transaction_date) as first_purchase_date,
                max(transaction_date) as last_purchase_date
            FROM main.stg_transactions
            WHERE direction = 'DEBIT' AND currency = ?
        """
        params: list[Any] = [currency]
        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += f" GROUP BY merchant_name ORDER BY total_spent DESC LIMIT {int(limit)}"
    else:
        query = """
            SELECT
                merchant_name,
                sum(total_spent) as total_spent,
                sum(transaction_count) as transaction_count,
                round(avg(avg_ticket_size), 2) as avg_ticket_size,
                min(first_purchase_date) as first_purchase_date,
                max(last_purchase_date) as last_purchase_date
            FROM main.gold_merchant_spending
            WHERE currency = ?
        """
        params = [currency]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += f" GROUP BY merchant_name ORDER BY total_spent DESC LIMIT {int(limit)}"

    with get_db_connection(db_path) as con:
        return con.execute(query, params).df()


def get_cashflow_summary(
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch inflow/outflow breakdown from gold_cashflow_summary."""
    query = """
        SELECT
            direction,
            sum(total_volume) as total_volume,
            sum(transaction_count) as transaction_count,
            round(avg(avg_amount), 2) as avg_amount,
            min(min_amount) as min_amount,
            max(max_amount) as max_amount
        FROM main.gold_cashflow_summary
        WHERE currency = ?
    """
    params: list[Any] = [currency]
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    query += " GROUP BY direction ORDER BY total_volume DESC"

    with get_db_connection(db_path) as con:
        return con.execute(query, params).df()


def get_filtered_transactions(
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    direction: str | None = None,
    merchant_search: str | None = None,
    currency: str = "INR",
    limit: int = 50,
    offset: int = 0,
    db_path: Path | None = None,
) -> tuple[pd.DataFrame, int]:
    """Retrieve paginated transaction records matching specific filters."""
    base_where = "WHERE currency = ?"
    params: list[Any] = [currency]

    if start_date:
        base_where += " AND transaction_date >= ?"
        params.append(start_date)
    if end_date:
        base_where += " AND transaction_date <= ?"
        params.append(end_date)
    if user_id:
        base_where += " AND user_id = ?"
        params.append(user_id)
    if direction and direction != "ALL":
        base_where += " AND direction = ?"
        params.append(direction)
    if merchant_search and merchant_search.strip():
        base_where += " AND lower(merchant_name) LIKE ?"
        params.append(f"%{merchant_search.strip().lower()}%")

    count_query = f"SELECT count(*) FROM main.stg_transactions {base_where}"

    data_query = f"""
        SELECT
            transaction_id,
            transaction_date,
            merchant_name,
            amount,
            currency,
            direction,
            source_type,
            reference_id
        FROM main.stg_transactions
        {base_where}
        ORDER BY transaction_date DESC, transaction_timestamp DESC
        LIMIT {int(limit)} OFFSET {int(offset)}
    """

    with get_db_connection(db_path) as con:
        total_count = con.execute(count_query, params).fetchone()[0]
        df = con.execute(data_query, params).df()

    return df, total_count


def get_data_freshness(db_path: Path | None = None) -> dict[str, Any]:
    """Check the latest update timestamp and total row count in the Silver table."""
    try:
        with get_db_connection(db_path) as con:
            res = con.execute(
                """
                SELECT
                    max(processed_at) as latest_processed_at,
                    count(*) as total_silver_rows
                FROM silver.transactions
                """
            ).fetchone()
            if not res or res[0] is None:
                return {"latest_processed_at": None, "total_rows": 0}
            return {
                "latest_processed_at": res[0],
                "total_rows": res[1],
            }
    except Exception as exc:
        logger.warning("Could not fetch data freshness: %s", exc)
        return {"latest_processed_at": None, "total_rows": 0}
