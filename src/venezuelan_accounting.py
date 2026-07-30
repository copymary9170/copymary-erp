"""Motor fiscal-contable venezolano, independiente de Streamlit.

Centraliza IVA, IGTF, retenciones, libros fiscales y partida doble. Los importes
se conservan en la moneda de la transacción y cada documento registra su tasa.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

MONEY = Decimal("0.01")


def money(value: object) -> Decimal:
    """Convierte y redondea un importe monetario a dos decimales."""
    try:
        return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise ValueError(f"Importe inválido: {value!r}") from exc


@dataclass(frozen=True)
class TaxAmounts:
    taxable_base: Decimal
    exempt_amount: Decimal
    vat_amount: Decimal
    igtf_amount: Decimal
    total: Decimal


def calculate_taxes(
    taxable_base: object,
    exempt_amount: object = 0,
    vat_rate: object = 16,
    igtf_rate: object = 3,
    payment_currency: str = "VES",
    payment_method: str = "",
) -> TaxAmounts:
    """Calcula IVA e IGTF; IGTF aplica solo a pagos en divisas o cripto."""
    base = money(taxable_base)
    exempt = money(exempt_amount)
    if base < 0 or exempt < 0:
        raise ValueError("La base imponible y el exento no pueden ser negativos.")
    vat = money(base * Decimal(str(vat_rate)) / 100)
    foreign = payment_currency.upper() != "VES" or payment_method.casefold() in {"cripto", "criptomoneda"}
    igtf_base = base + exempt + vat
    igtf = money(igtf_base * Decimal(str(igtf_rate)) / 100) if foreign else money(0)
    return TaxAmounts(base, exempt, vat, igtf, money(base + exempt + vat + igtf))


@dataclass(frozen=True)
class WithholdingAmounts:
    vat_withheld: Decimal
    islr_withheld: Decimal
    total_withheld: Decimal
    net_payable: Decimal


def calculate_withholdings(
    taxable_base: object,
    vat_amount: object,
    gross_total: object,
    vat_withholding_rate: object = 75,
    islr_rate: object = 0,
) -> WithholdingAmounts:
    """Calcula retenciones sobre IVA e ISLR sin permitir saldo neto negativo."""
    base = money(taxable_base)
    vat = money(vat_amount)
    gross = money(gross_total)
    vat_ret = money(vat * Decimal(str(vat_withholding_rate)) / 100)
    islr_ret = money(base * Decimal(str(islr_rate)) / 100)
    total = money(vat_ret + islr_ret)
    if total > gross:
        raise ValueError("Las retenciones no pueden superar el total del documento.")
    return WithholdingAmounts(vat_ret, islr_ret, total, money(gross - total))


@dataclass(frozen=True)
class JournalLine:
    account_code: str
    account_name: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    currency: str = "VES"
    exchange_rate: Decimal = Decimal("1.00")

    def __post_init__(self) -> None:
        if not self.account_code.strip() or not self.account_name.strip():
            raise ValueError("Cada línea requiere código y nombre de cuenta.")
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Débitos y créditos no pueden ser negativos.")
        if self.debit and self.credit:
            raise ValueError("Una línea no puede tener débito y crédito simultáneamente.")
        if self.exchange_rate <= 0:
            raise ValueError("La tasa de cambio debe ser mayor que cero.")

    @property
    def debit_ves(self) -> Decimal:
        return money(self.debit * self.exchange_rate)

    @property
    def credit_ves(self) -> Decimal:
        return money(self.credit * self.exchange_rate)


@dataclass(frozen=True)
class JournalEntry:
    entry_number: str
    entry_date: str
    description: str
    lines: tuple[JournalLine, ...]
    source_type: str = "manual"
    source_id: str = ""

    def validate(self) -> None:
        if len(self.lines) < 2:
            raise ValueError("Un asiento debe contener al menos dos líneas.")
        debit = sum((line.debit_ves for line in self.lines), Decimal("0.00"))
        credit = sum((line.credit_ves for line in self.lines), Decimal("0.00"))
        if money(debit) != money(credit):
            raise ValueError(f"Asiento descuadrado: débitos {money(debit)} != créditos {money(credit)}")


def ledger(entries: Iterable[JournalEntry]) -> dict[str, dict[str, Decimal | str]]:
    """Construye el Mayor en VES por cuenta a partir de asientos validados."""
    result: dict[str, dict[str, Decimal | str]] = {}
    for entry in entries:
        entry.validate()
        for line in entry.lines:
            row = result.setdefault(line.account_code, {"account_name": line.account_name, "debit": Decimal("0.00"), "credit": Decimal("0.00"), "balance": Decimal("0.00")})
            row["debit"] = money(Decimal(str(row["debit"])) + line.debit_ves)
            row["credit"] = money(Decimal(str(row["credit"])) + line.credit_ves)
            row["balance"] = money(Decimal(str(row["debit"])) - Decimal(str(row["credit"])))
    return result


def income_statement_from_ledger(ledger_rows: dict[str, dict[str, Decimal | str]]) -> dict[str, Decimal]:
    """Deriva ingresos, costos, gastos y resultado desde cuentas 4, 5 y 6."""
    revenue = costs = expenses = Decimal("0.00")
    for code, row in ledger_rows.items():
        balance = Decimal(str(row["balance"]))
        if code.startswith("4"):
            revenue += -balance
        elif code.startswith("5"):
            costs += balance
        elif code.startswith("6"):
            expenses += balance
    revenue, costs, expenses = map(money, (revenue, costs, expenses))
    return {"revenue": revenue, "costs": costs, "expenses": expenses, "net_income": money(revenue - costs - expenses)}


def sales_book(rows: Iterable[dict]) -> list[dict]:
    """Normaliza documentos de venta para exportación del Libro de Ventas IVA."""
    result: list[dict] = []
    for row in rows:
        tax = calculate_taxes(row.get("taxable_base", 0), row.get("exempt_amount", 0), row.get("vat_rate", 16), row.get("igtf_rate", 3), row.get("currency", "VES"), row.get("payment_method", ""))
        result.append({**row, "taxable_base": tax.taxable_base, "exempt_amount": tax.exempt_amount, "vat_amount": tax.vat_amount, "igtf_amount": tax.igtf_amount, "total": tax.total})
    return result


def purchase_book(rows: Iterable[dict]) -> list[dict]:
    """Normaliza documentos de compra para exportación del Libro de Compras IVA."""
    return sales_book(rows)


def next_control_number(last_number: str | None, prefix: str = "00-") -> str:
    """Genera el siguiente número de control preservando ancho numérico."""
    if not last_number:
        return f"{prefix}00000001"
    sequence = last_number[len(prefix):] if last_number.startswith(prefix) else last_number
    digits = "".join(ch for ch in sequence if ch.isdigit())
    if not digits:
        raise ValueError("El último número de control no contiene una secuencia numérica.")
    return f"{prefix}{int(digits) + 1:0{len(digits)}d}"
