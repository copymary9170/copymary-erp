"""Dominio puro para almacenes, transferencias, lotes y Kardex valorizado.

Esta capa no escribe directamente en Streamlit ni duplica la recepción. Está
pensada para ser usada por ``goods_receipt.py`` como única puerta de entrada de
compras y por los módulos de movimientos/despacho para salidas y transferencias.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

MONEY = Decimal("0.01")
QTY = Decimal("0.0001")
RECEIPT_SOURCE = "goods_receipt"


def _d(value: object) -> Decimal:
    return Decimal(str(value or 0))


def _q(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class StockMovement:
    movement_id: str
    item_id: str
    warehouse_id: str
    movement_date: date
    quantity: Decimal
    unit_cost: Decimal = Decimal("0")
    movement_type: str = "adjustment"
    reference: str = ""
    lot_id: str = ""
    source_module: str = ""

    @property
    def value(self) -> Decimal:
        return _q(self.quantity * self.unit_cost, MONEY)


@dataclass(frozen=True)
class KardexRow:
    movement_id: str
    movement_date: date
    warehouse_id: str
    reference: str
    entry_qty: Decimal
    exit_qty: Decimal
    balance_qty: Decimal
    unit_cost: Decimal
    movement_value: Decimal
    balance_value: Decimal
    average_cost: Decimal


def warehouse_stock(movements: Iterable[StockMovement], item_id: str, warehouse_id: str) -> Decimal:
    return _q(sum((m.quantity for m in movements if m.item_id == item_id and m.warehouse_id == warehouse_id), Decimal("0")), QTY)


def total_stock(movements: Iterable[StockMovement], item_id: str) -> Decimal:
    return _q(sum((m.quantity for m in movements if m.item_id == item_id), Decimal("0")), QTY)


def build_transfer(*, transfer_id: str, item_id: str, origin_warehouse_id: str,
                   destination_warehouse_id: str, quantity: object,
                   unit_cost: object, movement_date: date, lot_id: str = "") -> tuple[StockMovement, StockMovement]:
    qty = _d(quantity)
    if qty <= 0:
        raise ValueError("La cantidad transferida debe ser mayor que cero.")
    if origin_warehouse_id == destination_warehouse_id:
        raise ValueError("El almacén de origen y destino deben ser distintos.")
    cost = _d(unit_cost)
    common = dict(item_id=item_id, movement_date=movement_date, unit_cost=cost,
                  reference=transfer_id, lot_id=lot_id, source_module="warehouse_transfer")
    return (
        StockMovement(movement_id=f"{transfer_id}-OUT", warehouse_id=origin_warehouse_id,
                      quantity=-qty, movement_type="transfer_out", **common),
        StockMovement(movement_id=f"{transfer_id}-IN", warehouse_id=destination_warehouse_id,
                      quantity=qty, movement_type="transfer_in", **common),
    )


def validate_transfer(movements: Iterable[StockMovement], outgoing: StockMovement, incoming: StockMovement) -> None:
    if outgoing.reference != incoming.reference or outgoing.item_id != incoming.item_id:
        raise ValueError("Los movimientos de transferencia no pertenecen a la misma operación.")
    if outgoing.quantity + incoming.quantity != 0:
        raise ValueError("La salida y entrada de la transferencia no están cuadradas.")
    if warehouse_stock(movements, outgoing.item_id, outgoing.warehouse_id) + outgoing.quantity < 0:
        raise ValueError("Stock insuficiente en el almacén de origen.")


def ensure_receipt_source(source_module: str) -> None:
    if source_module != RECEIPT_SOURCE:
        raise ValueError("Las entradas por compra solo pueden originarse en goods_receipt.py.")


def ensure_not_duplicate_receipt(existing_movements: Iterable[StockMovement], receipt_reference: str, item_id: str) -> None:
    if any(m.source_module == RECEIPT_SOURCE and m.reference == receipt_reference and m.item_id == item_id for m in existing_movements):
        raise ValueError("Esta recepción ya fue aplicada al inventario.")


def lot_is_expired(expiration_date: date | str | None, on_date: date | None = None) -> bool:
    if not expiration_date:
        return False
    expiry = expiration_date if isinstance(expiration_date, date) else datetime.fromisoformat(str(expiration_date)[:10]).date()
    return expiry < (on_date or date.today())


def ensure_lot_dispatchable(expiration_date: date | str | None, on_date: date | None = None) -> None:
    if lot_is_expired(expiration_date, on_date):
        raise ValueError("No se puede despachar un lote vencido.")


def expiring_lots(lots: Iterable[dict], *, on_date: date | None = None, alert_days: int = 30) -> list[dict]:
    today = on_date or date.today()
    result = []
    for lot in lots:
        raw = lot.get("expiration_date") or lot.get("expiry_date") or lot.get("fecha_vencimiento")
        if not raw:
            continue
        expiry = raw if isinstance(raw, date) else datetime.fromisoformat(str(raw)[:10]).date()
        days = (expiry - today).days
        if days <= alert_days:
            row = dict(lot)
            row["days_to_expiry"] = days
            row["expiry_status"] = "expired" if days < 0 else "expiring"
            result.append(row)
    return sorted(result, key=lambda row: row["days_to_expiry"])


def build_kardex(movements: Iterable[StockMovement], item_id: str, warehouse_id: str | None = None) -> list[KardexRow]:
    selected = [m for m in movements if m.item_id == item_id and (warehouse_id is None or m.warehouse_id == warehouse_id)]
    selected.sort(key=lambda m: (m.movement_date, m.movement_id))
    qty_balance = Decimal("0")
    value_balance = Decimal("0")
    rows: list[KardexRow] = []
    for movement in selected:
        entry = max(movement.quantity, Decimal("0"))
        exit_qty = max(-movement.quantity, Decimal("0"))
        if movement.quantity > 0:
            movement_value = _q(movement.quantity * movement.unit_cost, MONEY)
            qty_balance += movement.quantity
            value_balance += movement_value
        else:
            average_before = value_balance / qty_balance if qty_balance else Decimal("0")
            movement_value = _q(exit_qty * average_before, MONEY)
            qty_balance -= exit_qty
            value_balance -= movement_value
        if qty_balance < 0:
            raise ValueError("El Kardex produce existencia negativa.")
        average = _q(value_balance / qty_balance, MONEY) if qty_balance else Decimal("0")
        rows.append(KardexRow(
            movement_id=movement.movement_id, movement_date=movement.movement_date,
            warehouse_id=movement.warehouse_id, reference=movement.reference,
            entry_qty=_q(entry, QTY), exit_qty=_q(exit_qty, QTY),
            balance_qty=_q(qty_balance, QTY), unit_cost=_q(movement.unit_cost, MONEY),
            movement_value=movement_value, balance_value=_q(value_balance, MONEY),
            average_cost=average,
        ))
    return rows
