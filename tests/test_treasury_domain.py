from datetime import date, timedelta
from decimal import Decimal

from src.treasury_domain import (
    CashTransaction,
    OpenBalance,
    aging_bucket,
    aging_report,
    cash_position,
    convert_to_base,
    due_projection,
)


def test_conversion_uses_transaction_rate():
    assert convert_to_base("10", "36.50") == Decimal("365.00")
    assert convert_to_base("20", "1.08") == Decimal("21.60")


def test_cash_position_groups_by_method_and_currency_and_reconciles():
    transactions = [
        CashTransaction("T1", date(2026, 7, 26), "Ingreso", Decimal("100"), "USD", Decimal("1"), "Zelle"),
        CashTransaction("T2", date(2026, 7, 26), "Ingreso", Decimal("5000"), "VES", Decimal("0.02"), "Pago móvil"),
        CashTransaction("T3", date(2026, 7, 26), "Egreso", Decimal("20"), "USD", Decimal("1"), "Zelle"),
        CashTransaction("T4", date(2026, 7, 26), "Ingreso", Decimal("50"), "EUR", Decimal("1.10"), "Tarjeta"),
    ]

    position = cash_position(transactions)

    assert position["by_method_currency"][("Zelle", "USD")] == Decimal("80.00")
    assert position["by_method_currency"][("Pago móvil", "VES")] == Decimal("5000.00")
    assert position["by_method_currency"][("Tarjeta", "EUR")] == Decimal("50.00")
    assert sum(position["by_method_base"].values()) == position["total_base"]
    assert position["total_base"] == Decimal("235.00")


def test_aging_bucket_ranges():
    as_of = date(2026, 7, 26)
    assert aging_bucket(as_of + timedelta(days=1), as_of) == "Al día"
    assert aging_bucket(as_of, as_of) == "0-30"
    assert aging_bucket(as_of - timedelta(days=30), as_of) == "0-30"
    assert aging_bucket(as_of - timedelta(days=31), as_of) == "31-60"
    assert aging_bucket(as_of - timedelta(days=60), as_of) == "31-60"
    assert aging_bucket(as_of - timedelta(days=61), as_of) == "61-90"
    assert aging_bucket(as_of - timedelta(days=90), as_of) == "61-90"
    assert aging_bucket(as_of - timedelta(days=91), as_of) == "+90"


def test_aging_report_totals_in_base_currency():
    as_of = date(2026, 7, 26)
    balances = [
        OpenBalance("AR-1", "C-1", "Por cobrar", as_of - timedelta(days=10), Decimal("100"), "USD", Decimal("1")),
        OpenBalance("AR-2", "C-2", "Por cobrar", as_of - timedelta(days=45), Decimal("2000"), "VES", Decimal("0.02")),
        OpenBalance("AP-1", "P-1", "Por pagar", as_of - timedelta(days=100), Decimal("50"), "EUR", Decimal("1.10")),
    ]

    report = aging_report(balances, as_of)

    assert report["totals"]["0-30"] == Decimal("100.00")
    assert report["totals"]["31-60"] == Decimal("40.00")
    assert report["totals"]["+90"] == Decimal("55.00")
    assert sum(report["totals"].values()) == Decimal("195.00")


def test_due_projection_accumulates_horizons_and_alerts_overdue():
    as_of = date(2026, 7, 26)
    balances = [
        OpenBalance("DUE-5", "C-1", "Por cobrar", as_of + timedelta(days=5), Decimal("10"), "USD", Decimal("1")),
        OpenBalance("DUE-12", "P-1", "Por pagar", as_of + timedelta(days=12), Decimal("20"), "USD", Decimal("1")),
        OpenBalance("DUE-25", "P-2", "Por pagar", as_of + timedelta(days=25), Decimal("30"), "USD", Decimal("1")),
        OpenBalance("LATE", "C-2", "Por cobrar", as_of - timedelta(days=40), Decimal("40"), "USD", Decimal("1")),
    ]

    result = due_projection(balances, as_of)

    assert result["projection"][7] == Decimal("10.00")
    assert result["projection"][15] == Decimal("30.00")
    assert result["projection"][30] == Decimal("60.00")
    assert result["overdue"] == Decimal("40.00")
    assert result["alerts"][0]["severity"] == "Crítica"


def test_invalid_rate_is_rejected():
    try:
        convert_to_base("10", "0")
    except ValueError as exc:
        assert "tasa" in str(exc).lower()
    else:
        raise AssertionError("Se esperaba ValueError por tasa inválida")
