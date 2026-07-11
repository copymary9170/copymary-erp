"""Reversión controlada de producciones registradas."""


from uuid import uuid4

import streamlit as st

from src.catalog_safe import aggregate_recipe
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows


def render_production_reversal() -> None:
    with st.container(border=True):
        render_page_header(
            "Reversos de producción",
            "Devuelve al inventario los materiales exactos usados en una producción anulada.",
        )
        st.caption("Las producciones nuevas guardan una copia de su receta y solo pueden revertirse una vez.")

    products = _rows("products_registry")
    inventory = _rows("inventory_registry")
    movements = _rows("inventory_movements")
    production_log = _rows("production_log")
    product_map = {str(item.get("product_id", "")): item for item in products}
    inventory_ids = {str(item.get("item_id", "")) for item in inventory}

    metrics = st.columns(4)
    metrics[0].metric("Producciones", str(len(production_log)))
    metrics[1].metric("Aplicadas", str(sum(1 for item in production_log if not item.get("reversed"))))
    metrics[2].metric("Revertidas", str(sum(1 for item in production_log if item.get("reversed"))))
    metrics[3].metric("Con receta guardada", str(sum(1 for item in production_log if item.get("recipe_snapshot"))))

    if not production_log:
        st.info("No hay producciones registradas.")
        return

    for production in reversed(production_log):
        production_id = str(production.get("production_id", ""))
        snapshot = aggregate_recipe(
            [dict(item) for item in production.get("recipe_snapshot", []) if isinstance(item, dict)]
        )
        source = "Receta guardada"
        if not snapshot:
            product = product_map.get(str(production.get("product_id", "")))
            snapshot = aggregate_recipe(
                [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
            ) if product else []
            source = "Receta actual de respaldo"

        with st.container(border=True):
            columns = st.columns(5)
            columns[0].metric("Producto", str(production.get("product_name", "")))
            columns[1].metric("Cantidad", f"{float(production.get('quantity', 0.0)):,.2f}")
            columns[2].metric("Costo total", format_money(float(production.get("total_cost", 0.0))))
            columns[3].metric("Estado", "Revertida" if production.get("reversed") else "Aplicada")
            missing_materials = [item["item_id"] for item in snapshot if item["item_id"] not in inventory_ids]
            disabled = bool(production.get("reversed")) or not snapshot or bool(missing_materials)
            reverse = columns[4].button(
                "Revertir",
                key=f"reverse_production_{production_id}",
                disabled=disabled,
                use_container_width=True,
            )
            st.caption(f"Base del reverso: {source}.")
            if not snapshot:
                st.error("No existe una receta disponible para calcular el reverso.")
            elif missing_materials:
                st.error("No se puede revertir porque uno o más materiales ya no existen en Inventario.")

            if reverse:
                required = {
                    item["item_id"]: item["quantity"] * float(production.get("quantity", 0.0))
                    for item in snapshot
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
                        item["recipe_snapshot"] = snapshot
                    updated_log.append(item)

                st.session_state["inventory_registry"] = updated_inventory
                st.session_state["inventory_movements"] = movements + new_movements
                st.session_state["production_log"] = updated_log
                st.rerun()

    render_info_card(
        "Trazabilidad",
        "Los materiales regresan como entradas vinculadas a la producción y se usa la receta guardada cuando está disponible.",
        "REVERSO CONTROLADO",
    )
