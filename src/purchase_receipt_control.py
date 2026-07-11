"""Recepción y reversión de compras con inventario trazable."""


from uuid import uuid4

import streamlit as st

from src import adjustments, purchasing
from src.session_utils import now_iso as _now


def _movements() -> list[dict]:
    return [
        dict(item)
        for item in st.session_state.get("inventory_movements", [])
        if isinstance(item, dict)
    ]


def _apply_purchase_with_movement(purchase: dict, inventory: list[dict]) -> list[dict]:
    purchase_id = str(purchase.get("purchase_id", ""))
    item_id = str(purchase.get("inventory_item_id", ""))
    quantity = float(purchase.get("quantity", 0.0))
    total_cost = float(purchase.get("total", 0.0))
    movements = _movements()

    if any(
        item.get("movement_type") == "Entrada"
        and str(item.get("reference", "")) == purchase_id
        for item in movements
    ):
        return inventory

    updated_inventory: list[dict] = []
    matched = False
    previous_quantity = 0.0
    resulting_quantity = quantity
    resolved_item_id = item_id
    item_name = str(purchase.get("material_name", "Material comprado"))
    unit_name = str(purchase.get("unit_name", "unidad"))

    for item in inventory:
        current = dict(item)
        if item_id and str(item.get("item_id", "")) == item_id:
            matched = True
            previous_quantity = float(item.get("available_quantity", 0.0))
            resulting_quantity = previous_quantity + quantity
            current["purchase_cost"] = float(item.get("purchase_cost", 0.0)) + total_cost
            current["purchased_quantity"] = float(item.get("purchased_quantity", 0.0)) + quantity
            current["available_quantity"] = resulting_quantity
            item_name = str(item.get("name", item_name))
            unit_name = str(item.get("unit_name", unit_name))
        updated_inventory.append(current)

    if not matched:
        resolved_item_id = item_id or uuid4().hex[:8]
        purchase["inventory_item_id"] = resolved_item_id
        updated_inventory.append(
            {
                "item_id": resolved_item_id,
                "name": item_name,
                "category": str(purchase.get("category", "Otro")),
                "purchase_cost": total_cost,
                "purchased_quantity": quantity,
                "available_quantity": quantity,
                "unit_name": unit_name,
                "minimum_stock": float(purchase.get("minimum_stock", 0.0)),
            }
        )

    movements.append(
        {
            "movement_id": uuid4().hex[:10],
            "created_at_utc": _now(),
            "item_id": resolved_item_id,
            "item_name": item_name,
            "movement_type": "Entrada",
            "quantity": quantity,
            "unit_name": unit_name,
            "reason": f"Recepción de compra {purchase_id}",
            "reference": purchase_id,
            "previous_quantity": previous_quantity,
            "resulting_quantity": resulting_quantity,
        }
    )
    st.session_state["inventory_movements"] = movements
    return updated_inventory


def _reverse_purchase_with_movement(
    purchase: dict,
    inventory: list[dict],
) -> tuple[list[dict], bool]:
    purchase_id = str(purchase.get("purchase_id", ""))
    item_id = str(purchase.get("inventory_item_id", ""))
    quantity = float(purchase.get("quantity", 0.0))
    total = float(purchase.get("total", 0.0))
    movements = _movements()

    if any(
        item.get("movement_type") == "Salida"
        and str(item.get("reference", "")) == f"REV-{purchase_id}"
        for item in movements
    ):
        return inventory, True

    updated_inventory: list[dict] = []
    reversed_ok = False
    item_name = str(purchase.get("material_name", "Material comprado"))
    unit_name = str(purchase.get("unit_name", "unidad"))
    previous_quantity = 0.0
    resulting_quantity = 0.0

    for item in inventory:
        current = dict(item)
        if item_id and str(item.get("item_id", "")) == item_id:
            previous_quantity = float(item.get("available_quantity", 0.0))
            if previous_quantity < quantity:
                return inventory, False
            resulting_quantity = previous_quantity - quantity
            current["available_quantity"] = resulting_quantity
            current["purchased_quantity"] = max(
                float(item.get("purchased_quantity", 0.0)) - quantity,
                0.0,
            )
            current["purchase_cost"] = max(
                float(item.get("purchase_cost", 0.0)) - total,
                0.0,
            )
            item_name = str(item.get("name", item_name))
            unit_name = str(item.get("unit_name", unit_name))
            reversed_ok = True
        updated_inventory.append(current)

    if reversed_ok:
        movements.append(
            {
                "movement_id": uuid4().hex[:10],
                "created_at_utc": _now(),
                "item_id": item_id,
                "item_name": item_name,
                "movement_type": "Salida",
                "quantity": quantity,
                "unit_name": unit_name,
                "reason": f"Reverso de recepción de compra {purchase_id}",
                "reference": f"REV-{purchase_id}",
                "previous_quantity": previous_quantity,
                "resulting_quantity": resulting_quantity,
            }
        )
        st.session_state["inventory_movements"] = movements

    return updated_inventory, reversed_ok


def activate_purchase_trace() -> None:
    purchasing._apply_purchase_to_inventory = _apply_purchase_with_movement
    adjustments._reverse_inventory = _reverse_purchase_with_movement


def render_purchases_with_trace() -> None:
    """Ejecuta Compras usando recepción trazable de inventario."""
    activate_purchase_trace()
    purchasing.render_purchases()
