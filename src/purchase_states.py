"""Estados de compra y de pago, y enlace Compras ↔ Catálogo (Fase 2 de la
separación Catálogo / Compras / Inventario).

Modela el ciclo de vida de una compra y de su pago como funciones puras y
testeables, y ofrece los ayudantes para que Compras seleccione artículos del
Catálogo por ``item_id`` en vez de por texto libre.

Principio: no se crean artículos de forma silenciosa desde una compra. Si el
artículo no existe, primero se crea en el Catálogo.
"""
from __future__ import annotations

from src.catalog_items import CatalogItem, find_by_id, get_catalog_items

PURCHASE_DRAFT = "Borrador"
PURCHASE_REQUESTED = "Solicitada"
PURCHASE_APPROVED = "Aprobada"
PURCHASE_ORDERED = "Ordenada"
PURCHASE_PARTIAL = "Parcialmente recibida"
PURCHASE_RECEIVED = "Recibida"
PURCHASE_CANCELLED = "Cancelada"
PURCHASE_CLOSED = "Cerrada"

PURCHASE_STATES = (
    PURCHASE_DRAFT, PURCHASE_REQUESTED, PURCHASE_APPROVED, PURCHASE_ORDERED,
    PURCHASE_PARTIAL, PURCHASE_RECEIVED, PURCHASE_CANCELLED, PURCHASE_CLOSED,
)

_PURCHASE_TRANSITIONS: dict[str, set[str]] = {
    PURCHASE_DRAFT: {PURCHASE_REQUESTED, PURCHASE_CANCELLED},
    PURCHASE_REQUESTED: {PURCHASE_APPROVED, PURCHASE_CANCELLED},
    PURCHASE_APPROVED: {PURCHASE_ORDERED, PURCHASE_CANCELLED},
    PURCHASE_ORDERED: {PURCHASE_PARTIAL, PURCHASE_RECEIVED, PURCHASE_CANCELLED},
    PURCHASE_PARTIAL: {PURCHASE_PARTIAL, PURCHASE_RECEIVED, PURCHASE_CANCELLED},
    PURCHASE_RECEIVED: {PURCHASE_CLOSED},
    PURCHASE_CANCELLED: set(),
    PURCHASE_CLOSED: set(),
}

PAYMENT_PENDING = "Pendiente"
PAYMENT_PARTIAL = "Parcial"
PAYMENT_PAID = "Pagada"
PAYMENT_OVERDUE = "Vencida"
PAYMENT_VOID = "Anulada"

PAYMENT_STATES = (
    PAYMENT_PENDING, PAYMENT_PARTIAL, PAYMENT_PAID, PAYMENT_OVERDUE, PAYMENT_VOID,
)


def can_transition(current: str, target: str) -> bool:
    return target in _PURCHASE_TRANSITIONS.get(current, set())


def next_states(current: str) -> tuple[str, ...]:
    return tuple(sorted(_PURCHASE_TRANSITIONS.get(current, set())))


def validate_purchase_line(
    *, quantity: float | None, unit_price: float | None = None,
    exchange_rate: float | None = None,
) -> list[str]:
    errors: list[str] = []
    if quantity is None or quantity <= 0:
        errors.append("La cantidad debe ser mayor que cero.")
    if unit_price is not None and unit_price < 0:
        errors.append("El precio unitario no puede ser negativo.")
    if exchange_rate is not None and exchange_rate <= 0:
        errors.append("El tipo de cambio debe ser mayor que cero.")
    return errors


def validate_reception(
    *, ordered: float, already_received: float, receiving_now: float,
    allow_over_receipt: bool = False,
) -> list[str]:
    errors: list[str] = []
    if receiving_now <= 0:
        errors.append("La cantidad recibida debe ser mayor que cero.")
    pending = ordered - already_received
    if not allow_over_receipt and receiving_now > pending + 1e-9:
        errors.append(f"No puedes recibir más de lo pendiente ({pending:g}).")
    return errors


def catalog_purchase_options(include_inactive: bool = False) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in get_catalog_items(include_inactive=include_inactive):
        label = f"{item.name} · {item.sku or item.item_id} · {item.inventory_unit}"
        options[label] = item.item_id
    return options


def resolve_purchase_article(purchase: dict) -> CatalogItem | None:
    return find_by_id(str(purchase.get("catalog_item_id", "")))


def link_fields_for(item: CatalogItem) -> dict:
    return {
        "catalog_item_id": item.item_id,
        "catalog_sku": item.sku,
        "material_name": item.name,
        "unit_name": item.inventory_unit,
    }
