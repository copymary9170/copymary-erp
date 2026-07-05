"""Reversión controlada de producciones registradas."""

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _aggregate(recipe: list[dict]) -> list[dict]:
    totals: dict[str, float] = {}
    for component in recipe:
        item_id = str(component.get("item_id", ""))
        quantity = float(component.get("quantity", 0.0))
        if item_id and quantity > 0:
            totals[item_id] = totals.get(item_id, 0.0) + quantity
    return [{"item_id": item_id, "quantity": quantity} for item_id, quantity in totals.items()]


def render_production_reversal() -> None:
    with st.container(border=True):
        render_page_header("Reversos de producción", "Devuelve al inventario los materiales de una producción anulada.")
        st.caption("Cada producción solo puede revertirse una vez.")

    products = _rows("products_registry")
    inventory = _rows("inventory_registry")
    movements = _rows("inventory_movements")
    production_log = _rows("production_log")
    product_map = {str(item.get("product_id", "")): item for item in products}

    metrics = st.columns(3)
    metrics[0].metric("Producciones", str(len(production_log)))
    metrics[1].metric("Aplicadas", str(sum(1 for item in production_log if not item.get("reversed"))))
    metrics[2].metric("Revertidas", str(sum(1 for item in production_log if item.get("reversed"))))

    if not production_log:
        st.info("No hay producciones registradas.")
        return

    for production in reversed(production_log):
        production_id = str(production.get("production_id", ""))
        with st.container(border=True):
            columns = st.columns(5)
            columns[0].metric("Producto", str(production.get("product_name", "")))
            columns[1].metric("Cantidad", f"{float(production.get('quantity', 0.0)):,.2f}")
            columns[2].metric("Costo total", format_money(float(production.get("total_cost", 0.0))))
            columns[3].metric("Estado", "Revertida" if production.get("reversed") else "Aplicada")
            reverse = columns[4].button(
                "Revertir",
                key=f"reverse_production_{production_id}",
                disabled=bool(production.get("reversed")),
                use_container_width=True,
            )

            if reverse:
                product = product_map.get(str(production.get("product_id", "")))
                if product is None:
                    st.error("No se puede revertir porque el producto ya no existe.")
                    continue
                recipe = _aggregate([dict(item) for item in product.get("recipe", []) if isinstance(item, dict)])
                required = {
                    item["item_id"]: item["quantity"] * float(production.get("quantity", 0.0))
                    for item in recipe
                }
                updated_inventory: list[dict] = []
                new_movements: list[dict] = []
                for material in inventory:
                    current = dict(material)
                    item_id = str(material.get("item_id", ""))
                    if item_id in required:
                        previous = float(material.get("available_quantity", 0.0))
                        restored = required[item_id]
                        current["available_quantity"] = previous + restored
                        new_movements.append({
                            "movement_id": uuid4().hex[:10],
                            "created_at_utc": _now(),
                            "item_id": item_id,
                            "item_name": str(material.get("name", "Material")),
                            "movement_type": "Entrada",
                            "quantity": restored,
                            "unit_name": str(material.get("unit_name", "unidad")),
                            "reason": f"Reverso de producción {production_id}",
                            "reference": production_id,
                            "previous_quantity": previous,
                            "resulting_quantity": previous + restored,
                        })
                    updated_inventory.append(current)

                updated_log = []
                for current in production_log:
                    item = dict(current)
                    if str(current.get("production_id", "")) == production_id:
                        item["reversed"] = True
                        item["reversed_at_utc"] = _now()
                    updated_log.append(item)

                st.session_state["inventory_registry"] = updated_inventory
                st.session_state["inventory_movements"] = movements + new_movements
                st.session_state["production_log"] = updated_log
                st.rerun()

    render_info_card("Trazabilidad", "Los materiales regresan como movimientos de entrada vinculados a la producción original.", "REVERSO CONTROLADO")
