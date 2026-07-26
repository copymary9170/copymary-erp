"""Dominio comercial puro para CopyMary ERP.

No modifica Streamlit ni registros existentes. Define contratos para conversión de
cotización a pedido/factura, descuentos autorizados, embudo CRM, ficha 360 y
segmentación reproducible.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

MONEY = Decimal("0.01")


def money(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CommercialLine:
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal("0.00")

    @property
    def gross(self) -> Decimal:
        return money(self.quantity * self.unit_price)

    @property
    def net(self) -> Decimal:
        return money(max(self.gross - self.discount, Decimal("0")))


@dataclass(frozen=True)
class CommercialDocument:
    document_id: str
    document_type: str
    customer_id: str
    currency: str
    exchange_rate: Decimal
    lines: tuple[CommercialLine, ...]
    tax_amount: Decimal = Decimal("0.00")
    other_charges: Decimal = Decimal("0.00")
    source_document_id: str | None = None
    status: str = "draft"

    @property
    def subtotal(self) -> Decimal:
        return money(sum((line.net for line in self.lines), Decimal("0")))

    @property
    def total(self) -> Decimal:
        return money(self.subtotal + self.tax_amount + self.other_charges)


def convert_document(source: CommercialDocument, target_type: str, target_id: str) -> CommercialDocument:
    """Convierte sin recapturar ni recalcular importes.

    Se copia el documento completo y solo cambian identidad, tipo, fuente y estado.
    """
    if target_type not in {"order", "invoice"}:
        raise ValueError("Tipo de documento destino no soportado")
    return replace(
        source,
        document_id=target_id,
        document_type=target_type,
        source_document_id=source.document_id,
        status="confirmed" if target_type == "order" else "issued",
        lines=tuple(deepcopy(source.lines)),
    )


def validate_conversion(source: CommercialDocument, target: CommercialDocument) -> None:
    if target.source_document_id != source.document_id:
        raise ValueError("El documento convertido no conserva la referencia de origen")
    if target.customer_id != source.customer_id or target.currency != source.currency:
        raise ValueError("La conversión modificó cliente o moneda")
    if target.exchange_rate != source.exchange_rate:
        raise ValueError("La conversión modificó la tasa de cambio")
    if target.lines != source.lines or target.subtotal != source.subtotal or target.total != source.total:
        raise ValueError("La conversión modificó líneas o importes")


@dataclass(frozen=True)
class DiscountPolicy:
    automatic_limit_percent: Decimal
    absolute_limit_percent: Decimal


def authorize_discount(
    subtotal: object,
    discount: object,
    policy: DiscountPolicy,
    approved_by: str | None = None,
) -> dict[str, object]:
    subtotal_value = money(subtotal)
    discount_value = money(discount)
    if subtotal_value <= 0 or discount_value < 0:
        raise ValueError("Subtotal y descuento inválidos")
    percent = (discount_value / subtotal_value * Decimal("100")).quantize(Decimal("0.01"))
    if percent > policy.absolute_limit_percent:
        raise ValueError("El descuento supera el tope absoluto")
    requires_approval = percent > policy.automatic_limit_percent
    if requires_approval and not approved_by:
        raise PermissionError("El descuento requiere autorización")
    return {
        "discount": discount_value,
        "discount_percent": percent,
        "requires_approval": requires_approval,
        "approved_by": approved_by if requires_approval else None,
    }


CRM_TRANSITIONS: dict[str, set[str]] = {
    "lead": {"qualified", "lost"},
    "qualified": {"opportunity", "lost"},
    "opportunity": {"quoted", "lost"},
    "quoted": {"won", "lost", "opportunity"},
    "won": set(),
    "lost": {"lead"},
}


def transition_crm(current: str, target: str) -> str:
    if target not in CRM_TRANSITIONS.get(current, set()):
        raise ValueError(f"Transición CRM inválida: {current} -> {target}")
    return target


def _as_date(value: object) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def customer_360(customer: dict, sales: Iterable[dict], as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    customer_id = str(customer.get("client_id") or customer.get("customer_id") or "")
    rows = [dict(row) for row in sales if str(row.get("client_id") or row.get("customer_id") or "") == customer_id]
    rows.sort(key=lambda row: str(row.get("created_at_utc") or row.get("date") or ""), reverse=True)
    total_purchases = money(sum((money(row.get("total")) for row in rows), Decimal("0")))
    outstanding = money(sum((money(row.get("total")) for row in rows if row.get("payment_status") != "Pagado"), Decimal("0")))
    last_purchase = _as_date(rows[0].get("created_at_utc") or rows[0].get("date")) if rows else None
    return {
        "customer_id": customer_id,
        "name": customer.get("name", ""),
        "purchase_count": len(rows),
        "total_purchases": total_purchases,
        "outstanding_balance": outstanding,
        "last_purchase_date": last_purchase,
        "days_since_last_purchase": (as_of - last_purchase).days if last_purchase else None,
        "last_orders": rows[:5],
        "preferences": customer.get("preferences", []),
        "birthday": customer.get("birthday"),
    }


def segment_customers(
    customers: Iterable[dict],
    sales: Iterable[dict],
    segment: str,
    as_of: date | None = None,
) -> list[dict]:
    as_of = as_of or date.today()
    profiles = [customer_360(customer, sales, as_of=as_of) for customer in customers]
    if segment == "all":
        return profiles
    if segment == "active":
        return [profile for profile in profiles if profile["days_since_last_purchase"] is not None and profile["days_since_last_purchase"] <= 90]
    if segment == "inactive":
        return [profile for profile in profiles if profile["days_since_last_purchase"] is None or profile["days_since_last_purchase"] > 90]
    if segment == "debtors":
        return [profile for profile in profiles if profile["outstanding_balance"] > 0]
    if segment == "frequent":
        return [profile for profile in profiles if profile["purchase_count"] >= 3]
    if segment == "birthday_month":
        return [profile for profile in profiles if _as_date(profile.get("birthday")) and _as_date(profile.get("birthday")).month == as_of.month]
    raise ValueError("Segmento no soportado")
