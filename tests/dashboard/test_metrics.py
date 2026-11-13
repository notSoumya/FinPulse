from decimal import Decimal

from dashboard.metrics import (
    calculate_avg_ticket,
    calculate_savings_rate,
    format_currency,
    format_number,
    format_pct,
)


def test_format_currency():
    assert format_currency(1234.5, "INR") == "₹1,234.50"
    assert format_currency(Decimal("50000.00"), "USD") == "$50,000.00"
    assert format_currency(99.99, "EUR") == "€99.99"
    assert format_currency(100, "GBP") == "GBP 100.00"
    assert format_currency(None) == "N/A"
    assert format_currency("not_a_number") == "N/A"


def test_format_pct():
    assert format_pct(95.456) == "95.46%"
    assert format_pct(0) == "0.00%"
    assert format_pct(None) == "N/A"


def test_format_number():
    assert format_number(1000) == "1,000"
    assert format_number(0) == "0"
    assert format_number(None) == "0"


def test_calculate_savings_rate():
    # 50,000 income, 2,000 expense -> (50000-2000)/50000 = 96.0%
    assert calculate_savings_rate(50000, 2000) == 96.0
    # Zero income -> None (distinguishes missing income from 0%)
    assert calculate_savings_rate(0, 1000) is None
    # Negative income -> None
    assert calculate_savings_rate(-100, 1000) is None
    # Expenses exceed income -> negative savings rate
    assert calculate_savings_rate(1000, 1500) == -50.0


def test_calculate_avg_ticket():
    assert calculate_avg_ticket(2500, 5) == 500.0
    assert calculate_avg_ticket(100, 0) is None
    assert calculate_avg_ticket(0, 10) == 0.0

