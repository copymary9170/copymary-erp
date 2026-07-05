"""Recepción de compras con movimientos de inventario trazables."""

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src import purchasing


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _apply_purchase_with_movement(purchase: dict, inventory: list[dict]) -> list[dict]:
    purchase_id = str(purchase.get("purchase_id", ""))
    item_id = str(purchase.get("inventory_item_id", ""))
    quantity = float(purchase.get("quantity", 0.0))
    total_cost = float(purchase.get("total", 0.0))
    movements = [
        dict(item)
        for item in st.session_state.get("inventory_movements", [])
        if isinstance(item, dict)
    ]

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


def render_purchases_with_trace() -> None:
    """Ejecuta Compras usando recepción trazable de inventario."""
    purchasing._apply_purchase_to_inventory = _apply_purchase_with_movement
    purchasing.render_purchases()
