from decimal import Decimal


def format_currency(amount: float | Decimal | None, currency: str = "INR") -> str:
    """Format monetary amount with 2 decimal places and currency symbol."""
    if amount is None:
        return "N/A"
    try:
        val = float(amount)
        if currency == "INR":
            return f"₹{val:,.2f}"
        elif currency == "USD":
            return f"${val:,.2f}"
        elif currency == "EUR":
            return f"€{val:,.2f}"
        return f"{currency} {val:,.2f}"
    except (ValueError, TypeError):
        return "N/A"


def format_pct(value: float | Decimal | None) -> str:
    """Format ratio or percentage to 2 decimal places."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_number(val: int | float | None) -> str:
    """Format integers or counts with thousands separator."""
    if val is None:
        return "0"
    return f"{int(val):,}"


def calculate_savings_rate(income: float | Decimal, expenses: float | Decimal) -> float | None:
    """
    Calculate savings rate percentage: (Income - Expenses) / Income * 100.
    Returns None if income <= 0 to distinguish missing data from genuine 0%.
    """
    inc = float(income or 0)
    exp = float(expenses or 0)
    if inc <= 0:
        return None
    return round(((inc - exp) / inc) * 100.0, 2)


def calculate_avg_ticket(expenses: float | Decimal, count: int) -> float | None:
    """Calculate average transaction value: Expenses / Count."""
    exp = float(expenses or 0)
    if count <= 0:
        return None
    return round(exp / count, 2)
