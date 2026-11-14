import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from dashboard.database import DatabaseUnavailableError, get_db_connection
from dashboard.metrics import calculate_avg_ticket, calculate_savings_rate

logger = logging.getLogger(__name__)


def _category_case_sql(col_name: str = "merchant_name") -> str:
    """Return standard SQL CASE statement for category mapping."""
    return f"""
        CASE
            WHEN lower({col_name}) LIKE '%amazon%'
                OR lower({col_name}) LIKE '%flipkart%' THEN 'Shopping'
            WHEN lower({col_name}) LIKE '%swiggy%'
                OR lower({col_name}) LIKE '%zomato%'
                OR lower({col_name}) LIKE '%blinkit%'
                OR lower({col_name}) LIKE '%instamart%' THEN 'Food & Groceries'
            WHEN lower({col_name}) LIKE '%uber%'
                OR lower({col_name}) LIKE '%ola%'
                OR lower({col_name}) LIKE '%metro%'
                OR lower({col_name}) LIKE '%irctc%' THEN 'Travel & Commute'
            WHEN lower({col_name}) LIKE '%salary%' THEN 'Income'
            ELSE 'Uncategorized'
        END
    """


def get_filter_bounds(db_path: Path | None = None) -> dict[str, Any]:
    """Retrieve available date ranges, users, currencies, categories, sources, and merchants."""
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
                min_d = date.today()
                max_d = date.today()
                users = []
                currencies = ["INR"]
            else:
                min_d = res[0]
                max_d = res[1]
                users = [u for u in (res[3] or []) if u]
                currencies = [c for c in (res[4] or []) if c]

            # Fetch auxiliary filter bounds if stg_transactions exists
            categories = [
                "Shopping",
                "Food & Groceries",
                "Travel & Commute",
                "Income",
                "Uncategorized",
            ]
            sources = ["UPI_CSV", "CARD_PDF", "BANK_SMS", "MANUAL"]
            merchants: list[str] = []
            months: list[str] = []

            try:
                m_sql = (
                    "SELECT DISTINCT merchant_name FROM main.stg_transactions "
                    "WHERE merchant_name IS NOT NULL ORDER BY 1"
                )
                m_rows = con.execute(m_sql).fetchall()
                merchants = [r[0] for r in m_rows if r[0]]

                mo_sql = (
                    "SELECT DISTINCT strftime(transaction_month, '%Y-%m') "
                    "FROM main.stg_transactions ORDER BY 1"
                )
                mo_rows = con.execute(mo_sql).fetchall()
                months = [r[0] for r in mo_rows if r[0]]

                s_sql = (
                    "SELECT DISTINCT source_type FROM main.stg_transactions "
                    "WHERE source_type IS NOT NULL ORDER BY 1"
                )
                s_rows = con.execute(s_sql).fetchall()
                if s_rows:
                    sources = [r[0] for r in s_rows if r[0]]
            except Exception:
                pass

            return {
                "min_date": min_d,
                "max_date": max_d,
                "users": users,
                "currencies": currencies if currencies else ["INR"],
                "categories": categories,
                "sources": sources,
                "merchants": merchants,
                "months": months,
            }
    except (DatabaseUnavailableError, Exception) as exc:
        logger.warning("Could not fetch filter bounds: %s", exc)
        return {
            "min_date": date.today(),
            "max_date": date.today(),
            "users": [],
            "currencies": ["INR"],
            "categories": [
                "Shopping",
                "Food & Groceries",
                "Travel & Commute",
                "Income",
                "Uncategorized",
            ],
            "sources": ["UPI_CSV", "CARD_PDF", "BANK_SMS", "MANUAL"],
            "merchants": [],
            "months": [],
        }


def get_overview_kpis(
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    currency: str = "INR",
    category: str | None = None,
    source_type: str | None = None,
    direction: str | None = None,
    merchant: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Fetch high-level KPI metrics for the selected time range and filters."""
    # If granular dimension filters are passed, query stg_transactions dynamically
    if category or source_type or (direction and direction != "ALL") or merchant:
        cat_expr = _category_case_sql("merchant_name")
        query = """
            SELECT
                coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0)
                    as total_income,
                coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0)
                    as total_expenses,
                coalesce(sum(case when direction = 'CREDIT' then amount else -amount end), 0)
                    as net_cash_flow,
                coalesce(sum(case when direction = 'DEBIT' then 1 else 0 end), 0) as debit_count,
                coalesce(sum(case when direction = 'CREDIT' then 1 else 0 end), 0) as credit_count,
                count(*) as total_transactions,
                max(transaction_date) as latest_date
            FROM main.stg_transactions
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
        if category and category != "All":
            query += f" AND {cat_expr} = ?"
            params.append(category)
        if source_type and source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)
        if direction and direction != "ALL":
            query += " AND direction = ?"
            params.append(direction)
        if merchant and merchant != "All":
            query += " AND lower(merchant_name) = lower(?)"
            params.append(merchant)
    else:
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
        params = [currency]
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
    category: str | None = None,
    source_type: str | None = None,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch daily time series for debit, credit, and net cash flow."""
    if category or source_type:
        cat_expr = _category_case_sql("merchant_name")
        query = """
            SELECT
                transaction_date,
                coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0) as expenses,
                coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0) as income,
                coalesce(sum(case when direction = 'CREDIT' then amount else -amount end), 0)
                    as net_cash_flow,
                count(*) as total_transactions
            FROM main.stg_transactions
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
        if category and category != "All":
            query += f" AND {cat_expr} = ?"
            params.append(category)
        if source_type and source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)
        query += " GROUP BY transaction_date ORDER BY transaction_date ASC"
    else:
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
        params = [currency]
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
    source_type: str | None = None,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch category-wise expenditure summary from gold_category_spending or stg_transactions."""
    if start_date or end_date or source_type:
        cat_expr = _category_case_sql("merchant_name")
        query = f"""
            SELECT
                {cat_expr} as spending_category,
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
        if source_type and source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)

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


def get_spending_by_source(
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch spending breakdown grouped by transaction source channel."""
    query = """
        SELECT
            source_type,
            sum(case when direction = 'DEBIT' then amount else 0 end) as total_debit,
            sum(case when direction = 'CREDIT' then amount else 0 end) as total_credit,
            count(*) as total_transactions
        FROM main.stg_transactions
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

    query += " GROUP BY source_type ORDER BY total_debit DESC"

    with get_db_connection(db_path) as con:
        return con.execute(query, params).df()


def get_financial_insights(
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> list[dict[str, str]]:
    """Generate dynamic, data-driven analytical insights derived directly from warehouse tables."""
    insights: list[dict[str, str]] = []
    try:
        with get_db_connection(db_path) as con:
            # 1. Highest spending category
            cat_row = con.execute(
                """
                SELECT spending_category, total_spent
                FROM main.gold_category_spending
                WHERE currency = ? AND (? IS NULL OR user_id = ?)
                ORDER BY total_spent DESC
                LIMIT 1
                """,
                [currency, user_id, user_id],
            ).fetchone()

            if cat_row:
                cat_amt = float(cat_row[1])
                insights.append(
                    {
                        "title": "Top Expenditure Category",
                        "text": (
                            f"Your highest spending category is **{cat_row[0]}** "
                            f"with total expenses of **{currency} {cat_amt:,.2f}**."
                        ),
                        "type": "info",
                    }
                )

            # 2. Highest spending merchant
            merch_row = con.execute(
                """
                SELECT merchant_name, total_spent, transaction_count
                FROM main.gold_merchant_spending
                WHERE currency = ? AND (? IS NULL OR user_id = ?)
                ORDER BY total_spent DESC
                LIMIT 1
                """,
                [currency, user_id, user_id],
            ).fetchone()

            if merch_row:
                m_amt = float(merch_row[1])
                insights.append(
                    {
                        "title": "Dominant Merchant",
                        "text": (
                            f"**{merch_row[0]}** represents your largest single-merchant "
                            f"outflow, totaling **{currency} {m_amt:,.2f}** "
                            f"across {merch_row[2]} transactions."
                        ),
                        "type": "info",
                    }
                )

            # 3. Monthly expense and savings trajectory
            monthly_rows = con.execute(
                """
                SELECT
                    strftime(transaction_month, '%B %Y') as m_name,
                    monthly_expenses,
                    monthly_income,
                    net_savings,
                    savings_rate_pct
                FROM main.gold_monthly_spending
                WHERE currency = ? AND (? IS NULL OR user_id = ?)
                ORDER BY transaction_month ASC
                """,
                [currency, user_id, user_id],
            ).fetchall()

            if monthly_rows:
                # Find month with highest expenses
                max_exp_month = max(monthly_rows, key=lambda r: float(r[1]))
                p_amt = float(max_exp_month[1])
                insights.append(
                    {
                        "title": "Peak Expense Month",
                        "text": (
                            f"Peak outflow occurred in **{max_exp_month[0]}** "
                            f"with expenses reaching **{currency} {p_amt:,.2f}**."
                        ),
                        "type": "warning" if float(max_exp_month[3]) < 0 else "info",
                    }
                )

                if len(monthly_rows) >= 2:
                    prev_m = monthly_rows[-2]
                    curr_m = monthly_rows[-1]
                    exp_diff = float(curr_m[1]) - float(prev_m[1])
                    pct_change = (
                        (exp_diff / float(prev_m[1]) * 100) if float(prev_m[1]) > 0 else 0
                    )
                    direction_str = "increased" if exp_diff > 0 else "decreased"
                    p_prev = float(prev_m[1])
                    p_curr = float(curr_m[1])
                    insights.append(
                        {
                            "title": "Monthly Expense Trajectory",
                            "text": (
                                f"Outflows **{direction_str} by {abs(pct_change):.1f}%** from "
                                f"{prev_m[0]} ({currency} {p_prev:,.2f}) to "
                                f"{curr_m[0]} ({currency} {p_curr:,.2f})."
                            ),
                            "type": "warning" if exp_diff > 0 else "success",
                        }
                    )

                # Overall savings rate
                rates = [float(r[4]) for r in monthly_rows if r[4] is not None]
                avg_rate = sum(rates) / max(len(rates), 1)
                insights.append(
                    {
                        "title": "Savings Resilience",
                        "text": (
                            f"Your average monthly savings rate over the period is "
                            f"**{avg_rate:.1f}%**, reflecting robust capital retention."
                        ),
                        "type": "success" if avg_rate >= 30 else "info",
                    }
                )

    except Exception as exc:
        logger.warning("Could not compute financial insights: %s", exc)

    return insights


def _has_anomalies_table(con: Any) -> bool:
    """Check if silver.anomalies exists in DuckDB."""
    try:
        chk_sql = (
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'silver' AND table_name = 'anomalies'"
        )
        return con.execute(chk_sql).fetchone()[0] > 0
    except Exception:
        return False


def get_anomaly_kpis(
    user_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Fetch summary metrics for ML anomaly detection."""
    default_res = {
        "total_anomalies": 0,
        "high_severity_count": 0,
        "medium_severity_count": 0,
        "low_severity_count": 0,
        "total_evaluated": 0,
        "anomaly_pct": 0.0,
    }
    try:
        with get_db_connection(db_path) as con:
            if not _has_anomalies_table(con):
                return default_res

            query = """
                SELECT
                    count(*) as total_evaluated,
                    coalesce(sum(case when a.is_anomaly then 1 else 0 end), 0)
                        as total_anomalies,
                    coalesce(sum(case when a.severity = 'High' then 1 else 0 end), 0)
                        as high_count,
                    coalesce(sum(case when a.severity = 'Medium' then 1 else 0 end), 0)
                        as med_count,
                    coalesce(sum(case when a.severity = 'Low' then 1 else 0 end), 0)
                        as low_count
                FROM main.stg_transactions t
                JOIN silver.anomalies a ON t.transaction_id = a.transaction_id
                WHERE t.currency = ?
            """
            params: list[Any] = [currency]
            if user_id:
                query += " AND t.user_id = ?"
                params.append(user_id)
            if start_date:
                query += " AND t.transaction_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND t.transaction_date <= ?"
                params.append(end_date)

            row = con.execute(query, params).fetchone()
            if not row or row[0] == 0:
                return default_res

            total_eval = int(row[0])
            total_anom = int(row[1])
            return {
                "total_evaluated": total_eval,
                "total_anomalies": total_anom,
                "high_severity_count": int(row[2]),
                "medium_severity_count": int(row[3]),
                "low_severity_count": int(row[4]),
                "anomaly_pct": round((total_anom / total_eval * 100), 2) if total_eval > 0 else 0.0,
            }
    except Exception as exc:
        logger.warning("Error fetching anomaly KPIs: %s", exc)
        return default_res


def get_anomaly_timeline(
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch daily time-series of anomalous versus normal transactions."""
    try:
        with get_db_connection(db_path) as con:
            if not _has_anomalies_table(con):
                return pd.DataFrame()

            query = """
                SELECT
                    t.transaction_date,
                    coalesce(sum(case when a.is_anomaly then 1 else 0 end), 0) as anomalies_count,
                    coalesce(sum(case when not a.is_anomaly then 1 else 0 end), 0) as normal_count,
                    round(avg(a.anomaly_score), 3) as avg_anomaly_score
                FROM main.stg_transactions t
                JOIN silver.anomalies a ON t.transaction_id = a.transaction_id
                WHERE t.currency = ?
            """
            params: list[Any] = [currency]
            if user_id:
                query += " AND t.user_id = ?"
                params.append(user_id)
            query += " GROUP BY t.transaction_date ORDER BY t.transaction_date ASC"
            return con.execute(query, params).df()
    except Exception as exc:
        logger.warning("Error fetching anomaly timeline: %s", exc)
        return pd.DataFrame()


def get_anomaly_distributions(
    dimension: str = "category",
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch breakdown of anomalies across category, merchant, or source."""
    cat_expr = _category_case_sql("t.merchant_name")
    if dimension == "category":
        dim_col = f"{cat_expr} as label"
    elif dimension == "merchant":
        dim_col = "t.merchant_name as label"
    else:
        dim_col = "t.source_type as label"

    try:
        with get_db_connection(db_path) as con:
            if not _has_anomalies_table(con):
                return pd.DataFrame()

            query = f"""
                SELECT
                    {dim_col},
                    count(*) as anomaly_count,
                    round(avg(t.amount), 2) as avg_amount,
                    round(avg(a.anomaly_score), 3) as avg_score
                FROM main.stg_transactions t
                JOIN silver.anomalies a ON t.transaction_id = a.transaction_id
                WHERE a.is_anomaly = true AND t.currency = ?
            """
            params: list[Any] = [currency]
            if user_id:
                query += " AND t.user_id = ?"
                params.append(user_id)
            query += " GROUP BY 1 ORDER BY anomaly_count DESC LIMIT 10"
            return con.execute(query, params).df()
    except Exception as exc:
        logger.warning("Error fetching anomaly distribution: %s", exc)
        return pd.DataFrame()


def get_anomaly_investigation_records(
    user_id: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    currency: str = "INR",
    limit: int = 50,
    offset: int = 0,
    db_path: Path | None = None,
) -> tuple[pd.DataFrame, int]:
    """Retrieve filtered anomalous transaction records with full explainability metadata."""
    try:
        with get_db_connection(db_path) as con:
            if not _has_anomalies_table(con):
                return pd.DataFrame(), 0

            cat_expr = _category_case_sql("t.merchant_name")
            base_where = "WHERE a.is_anomaly = true AND t.currency = ?"
            params: list[Any] = [currency]

            if user_id:
                base_where += " AND t.user_id = ?"
                params.append(user_id)
            if severity and severity != "All":
                base_where += " AND a.severity = ?"
                params.append(severity)
            if category and category != "All":
                base_where += f" AND {cat_expr} = ?"
                params.append(category)
            if start_date:
                base_where += " AND t.transaction_date >= ?"
                params.append(start_date)
            if end_date:
                base_where += " AND t.transaction_date <= ?"
                params.append(end_date)

            count_query = f"""
                SELECT count(*)
                FROM main.stg_transactions t
                JOIN silver.anomalies a ON t.transaction_id = a.transaction_id
                {base_where}
            """
            total_count = con.execute(count_query, params).fetchone()[0]

            data_query = f"""
                SELECT
                    t.transaction_id,
                    t.transaction_date,
                    t.user_id,
                    t.merchant_name,
                    t.amount,
                    t.direction,
                    {cat_expr} as category,
                    t.source_type,
                    a.anomaly_score,
                    a.severity,
                    a.primary_reason,
                    a.contributing_signals,
                    a.model_version
                FROM main.stg_transactions t
                JOIN silver.anomalies a ON t.transaction_id = a.transaction_id
                {base_where}
                ORDER BY a.anomaly_score DESC, t.transaction_date DESC
                LIMIT {int(limit)} OFFSET {int(offset)}
            """
            df = con.execute(data_query, params).df()
            return df, total_count
    except Exception as exc:
        logger.warning("Error fetching anomaly investigation records: %s", exc)
        return pd.DataFrame(), 0


def get_anomaly_normal_comparison(
    user_id: str | None = None,
    currency: str = "INR",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Generate comparative summary between normal and anomalous transaction cohorts."""
    default_stats = {
        "normal_count": 0,
        "normal_avg_amount": 0.0,
        "normal_max_amount": 0.0,
        "anomalous_count": 0,
        "anomalous_avg_amount": 0.0,
        "anomalous_max_amount": 0.0,
    }
    try:
        with get_db_connection(db_path) as con:
            if not _has_anomalies_table(con):
                return default_stats

            query = """
                SELECT
                    a.is_anomaly,
                    count(*) as tx_count,
                    round(avg(t.amount), 2) as avg_amount,
                    max(t.amount) as max_amount
                FROM main.stg_transactions t
                JOIN silver.anomalies a ON t.transaction_id = a.transaction_id
                WHERE t.currency = ? AND (? IS NULL OR t.user_id = ?)
                GROUP BY a.is_anomaly
            """
            rows = con.execute(query, [currency, user_id, user_id]).fetchall()
            for row in rows:
                is_anom, count, avg_amt, max_amt = row
                if is_anom:
                    default_stats["anomalous_count"] = int(count)
                    default_stats["anomalous_avg_amount"] = float(avg_amt)
                    default_stats["anomalous_max_amount"] = float(max_amt)
                else:
                    default_stats["normal_count"] = int(count)
                    default_stats["normal_avg_amount"] = float(avg_amt)
                    default_stats["normal_max_amount"] = float(max_amt)
            return default_stats
    except Exception as exc:
        logger.warning("Error comparing normal and anomalous cohorts: %s", exc)
        return default_stats


def get_filtered_transactions(
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    direction: str | None = None,
    merchant_search: str | None = None,
    category: str | None = None,
    source_type: str | None = None,
    currency: str = "INR",
    limit: int = 50,
    offset: int = 0,
    db_path: Path | None = None,
) -> tuple[pd.DataFrame, int]:
    """
    Retrieve paginated transaction records matching specific filters,
    including anomaly indicators.
    """
    cat_expr = _category_case_sql("merchant_name")
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
    if category and category != "All":
        base_where += f" AND {cat_expr} = ?"
        params.append(category)
    if source_type and source_type != "All":
        base_where += " AND source_type = ?"
        params.append(source_type)

    with get_db_connection(db_path) as con:
        has_anom = _has_anomalies_table(con)

        count_query = f"SELECT count(*) FROM main.stg_transactions {base_where}"
        total_count = con.execute(count_query, params).fetchone()[0]

        if has_anom:
            where_t = (
                base_where.replace("merchant_name", "t.merchant_name")
                .replace("transaction_date", "t.transaction_date")
                .replace("currency", "t.currency")
                .replace("user_id", "t.user_id")
                .replace("direction", "t.direction")
                .replace("source_type", "t.source_type")
            )
            data_query = f"""
                SELECT
                    t.transaction_id,
                    t.transaction_date,
                    t.merchant_name,
                    t.amount,
                    t.currency,
                    t.direction,
                    {_category_case_sql("t.merchant_name")} as category,
                    t.source_type,
                    t.reference_id,
                    coalesce(a.is_anomaly, false) as is_anomaly,
                    coalesce(a.anomaly_score, 0.0) as anomaly_score,
                    coalesce(a.severity, 'Normal') as severity
                FROM main.stg_transactions t
                LEFT JOIN silver.anomalies a ON t.transaction_id = a.transaction_id
                {where_t}
                ORDER BY t.transaction_date DESC, t.transaction_timestamp DESC
                LIMIT {int(limit)} OFFSET {int(offset)}
            """
        else:
            data_query = f"""
                SELECT
                    transaction_id,
                    transaction_date,
                    merchant_name,
                    amount,
                    currency,
                    direction,
                    {cat_expr} as category,
                    source_type,
                    reference_id
                FROM main.stg_transactions
                {base_where}
                ORDER BY transaction_date DESC, transaction_timestamp DESC
                LIMIT {int(limit)} OFFSET {int(offset)}
            """

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
