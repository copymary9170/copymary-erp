"""Dominio puro de tesorería: multimoneda, posición de caja y aging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


MONEY = Decimal("0.01")
SUPPORTED_CURRENCIES = {"USD", "VES", "EUR"}
SUPPORTED_METHODS = {"Efectivo", "Pago móvil", "Zelle", "Kontigo", "Tarjeta", "Otro"}
AGING_BUCKETS = ("Al día", "0-30", "31-60", "61-90", "+90")


def _decimal(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal | int | float | str) -> Decimal:
    return _decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CashTransaction:
    transaction_id: str
    transaction_date: date
    movement_type: str
    amount: Decimal
    currency: str
    exchange_rate: Decimal
    payment_method: str
    reference: str = ""

    def __post_init__(self) -> None:
        if self.movement_type not in {"Ingreso", "Egreso"}:
            raise ValueError("El movimiento debe ser Ingreso o Egreso.")
        if self.currency not in SUPPORTED_CURRENCIES:
            raise ValueError("Moneda no soportada.")
        if self.payment_method not in SUPPORTED_METHODS:
            raise ValueError("Método de pago no soportado.")
        if _decimal(self.amount) <= 0:
            raise ValueError("El monto debe ser mayor que cero.")
        if _decimal(self.exchange_rate) <= 0:
            raise ValueError("La tasa de cambio debe ser mayor que cero.")

    @property
    def signed_amount(self) -> Decimal:
        amount = _money(self.amount)
        return amount if self.movement_type == "Ingreso" else -amount

    @property
    def base_amount(self) -> Decimal:
        """Monto firmado convertido a la moneda base con la tasa de la transacción."""
        return _money(self.signed_amount * _decimal(self.exchange_rate))


@dataclass(frozen=True)
class OpenBalance:
    document_id: str
    counterparty_id: str
    balance_type: str
    due_date: date
    amount: Decimal
    currency: str
    exchange_rate: Decimal

    def __post_init__(self) -> None:
        if self.balance_type not in {"Por cobrar", "Por pagar"}:
            raise ValueError("Tipo de saldo no soportado.")
        if self.currency not in SUPPORTED_CURRENCIES:
            raise ValueError("Moneda no soportada.")
        if _decimal(self.amount) < 0:
            raise ValueError("El saldo no puede ser negativo.")
        if _decimal(self.exchange_rate) <= 0:
            raise ValueError("La tasa debe ser mayor que cero.")

    @property
    def base_amount(self) -> Decimal:
        return _money(_decimal(self.amount) * _decimal(self.exchange_rate))


def convert_to_base(amount: Decimal | int | float | str, exchange_rate: Decimal | int | float | str) -> Decimal:
    if _decimal(exchange_rate) <= 0:
        raise ValueError("La tasa de cambio debe ser mayor que cero.")
    return _money(_decimal(amount) * _decimal(exchange_rate))


def cash_position(transactions: Iterable[CashTransaction]) -> dict:
    by_method_currency: dict[tuple[str, str], Decimal] = {}
    by_currency: dict[str, Decimal] = {}
    by_method_base: dict[str, Decimal] = {}
    total_base = Decimal("0.00")

    for transaction in transactions:
        key = (transaction.payment_method, transaction.currency)
        by_method_currency[key] = _money(by_method_currency.get(key, Decimal("0")) + transaction.signed_amount)
        by_currency[transaction.currency] = _money(
            by_currency.get(transaction.currency, Decimal("0")) + transaction.signed_amount
        )
        by_method_base[transaction.payment_method] = _money(
            by_method_base.get(transaction.payment_method, Decimal("0")) + transaction.base_amount
        )
        total_base = _money(total_base + transaction.base_amount)

    return {
        "by_method_currency": by_method_currency,
        "by_currency": by_currency,
        "by_method_base": by_method_base,
        "total_base": total_base,
    }


def aging_bucket(due_date: date, as_of: date) -> str:
    days_overdue = (as_of - due_date).days
    if days_overdue < 0:
        return "Al día"
    if days_overdue <= 30:
        return "0-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "+90"


def aging_report(balances: Iterable[OpenBalance], as_of: date) -> dict:
    totals = {bucket: Decimal("0.00") for bucket in AGING_BUCKETS}
    counts = {bucket: 0 for bucket in AGING_BUCKETS}
    details: list[dict] = []

    for balance in balances:
        if _decimal(balance.amount) <= 0:
            continue
        bucket = aging_bucket(balance.due_date, as_of)
        totals[bucket] = _money(totals[bucket] + balance.base_amount)
        counts[bucket] += 1
        details.append(
            {
                "document_id": balance.document_id,
                "counterparty_id": balance.counterparty_id,
                "balance_type": balance.balance_type,
                "due_date": balance.due_date,
                "days_overdue": max((as_of - balance.due_date).days, 0),
                "bucket": bucket,
                "amount": _money(balance.amount),
                "currency": balance.currency,
                "exchange_rate": _decimal(balance.exchange_rate),
                "base_amount": balance.base_amount,
            }
        )

    return {"totals": totals, "counts": counts, "details": details}


def due_projection(balances: Iterable[OpenBalance], as_of: date, horizons: tuple[int, ...] = (7, 15, 30)) -> dict:
    projection = {days: Decimal("0.00") for days in horizons}
    overdue = Decimal("0.00")
    alerts: list[dict] = []

    for balance in balances:
        if _decimal(balance.amount) <= 0:
            continue
        days_to_due = (balance.due_date - as_of).days
        if days_to_due < 0:
            overdue = _money(overdue + balance.base_amount)
            alerts.append({
                "document_id": balance.document_id,
                "severity": "Crítica" if days_to_due < -30 else "Alta",
                "message": f"Saldo vencido hace {abs(days_to_due)} día(s).",
                "base_amount": balance.base_amount,
            })
            continue
        for horizon in horizons:
            if days_to_due <= horizon:
                projection[horizon] = _money(projection[horizon] + balance.base_amount)

    return {"projection": projection, "overdue": overdue, "alerts": alerts}
