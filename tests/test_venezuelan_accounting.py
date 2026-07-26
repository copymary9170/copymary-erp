from decimal import Decimal

import pytest

from src.venezuelan_accounting import (
    JournalEntry,
    JournalLine,
    calculate_taxes,
    calculate_withholdings,
    income_statement_from_ledger,
    ledger,
    next_control_number,
    sales_book,
)


def test_calculo_iva_e_igtf_en_divisas():
    result = calculate_taxes(100, 20, 16, 3, "USD")
    assert result.vat_amount == Decimal("16.00")
    assert result.igtf_amount == Decimal("4.08")
    assert result.total == Decimal("140.08")


def test_igtf_no_aplica_en_ves():
    result = calculate_taxes(100, 0, 16, 3, "VES")
    assert result.igtf_amount == Decimal("0.00")
    assert result.total == Decimal("116.00")


def test_retenciones_iva_e_islr():
    result = calculate_withholdings(100, 16, 116, 75, 2)
    assert result.vat_withheld == Decimal("12.00")
    assert result.islr_withheld == Decimal("2.00")
    assert result.net_payable == Decimal("102.00")


def test_asiento_debe_cuadrar_en_ves_con_multimoneda():
    entry = JournalEntry(
        "ASI-1",
        "2026-07-26",
        "Venta en USD",
        (
            JournalLine("1.1.01", "Caja USD", debit=Decimal("116"), currency="USD", exchange_rate=Decimal("40")),
            JournalLine("4.1.01", "Ventas", credit=Decimal("100"), currency="USD", exchange_rate=Decimal("40")),
            JournalLine("2.1.01", "IVA débito fiscal", credit=Decimal("16"), currency="USD", exchange_rate=Decimal("40")),
        ),
    )
    entry.validate()
    mayor = ledger([entry])
    assert mayor["1.1.01"]["debit"] == Decimal("4640.00")


def test_asiento_descuadrado_falla():
    entry = JournalEntry(
        "ASI-2", "2026-07-26", "Error",
        (JournalLine("1", "Caja", debit=Decimal("10")), JournalLine("4", "Ventas", credit=Decimal("9"))),
    )
    with pytest.raises(ValueError, match="descuadrado"):
        entry.validate()


def test_estado_resultados_deriva_del_mayor():
    entry = JournalEntry(
        "ASI-3", "2026-07-26", "Resultado",
        (
            JournalLine("1.1", "Caja", debit=Decimal("100")),
            JournalLine("4.1", "Ventas", credit=Decimal("100")),
            JournalLine("5.1", "Costo de ventas", debit=Decimal("40")),
            JournalLine("1.2", "Inventario", credit=Decimal("40")),
        ),
    )
    statement = income_statement_from_ledger(ledger([entry]))
    assert statement["revenue"] == Decimal("100.00")
    assert statement["costs"] == Decimal("40.00")
    assert statement["net_income"] == Decimal("60.00")


def test_libro_ventas_suma_igual_ventas_periodo():
    rows = sales_book([
        {"document": "F-1", "taxable_base": 100, "exempt_amount": 0, "currency": "VES"},
        {"document": "F-2", "taxable_base": 50, "exempt_amount": 10, "currency": "VES"},
    ])
    assert sum(row["total"] for row in rows) == Decimal("184.00")


def test_numeracion_control_secuencial():
    assert next_control_number("00-00000009") == "00-00000010"
