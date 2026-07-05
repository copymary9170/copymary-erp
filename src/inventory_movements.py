"""Movimientos temporales de inventario con historial para CopyMary ERP."""

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header


def _get_items() -> list[dict]:
    items: list[dict] = []
    for raw_item in st.session_state.get("inventory_registry", []):
        if isinstance(raw_item, dict):
            items.append(dict(raw_item))
        else:
            items.append(
                {
                    "item_id": getattr(raw_item, "item_id", ""),
                    "name": getattr(raw_item, "name", "Material"),
                    "category": getattr(raw_item, "category", "Otro"),
                    "purchase_cost": float(getattr(raw_item, "purchase_cost", 0.0)),
                    "purchased_quantity": float(getattr(raw_item, "purchased_quantity", 1.0)),
                    "available_quantity": float(getattr(raw_item, "available_quantity", 0.0)),
                    "unit_name": getattr(raw_item, "unit_name", "unidad"),
                    "minimum_stock": float(getattr(raw_item, "minimum_stock", 0.0)),
                }
            )
    return items


def _get_movements() -> list[dict]:
    raw_movements = st.session_state.get("inventory_movements", [])
    return [dict(item) for item in raw_movements if isinstance(item, dict)]


def _save_items(items: list[dict]) -> None:
    st.session_state.inventory_registry = items


def _save_movements(movements: list[dict]) -> None:
    st.session_state.inventory_movements = movements


def _apply_movement(
    items: list[dict],
    item_id: str,
    movement_type: str,
    quantity: float,
) -> tuple[list[dict], float, float]:
    updated_items: list[dict] = []
    previous_quantity = 0.0
    resulting_quantity = 0.0

    for item in items:
        updated_item = dict(item)
        if str(item.get("item_id", "")) == item_id:
            previous_quantity = float(item.get("available_quantity", 0.0))
            if movement_type == "Entrada":
                resulting_quantity = previous_quantity + quantity
            else:
                resulting_quantity = previous_quantity - quantity
            updated_item["available_quantity"] = resulting_quantity
        updated_items.append(updated_item)

    return updated_items, previous_quantity, resulting_quantity


def render_inventory_movements() -> None:
    """Renderiza movimientos de inventario con trazabilidad temporal."""
    with st.container(border=True):
        render_page_header(
            "Movimientos de inventario",
            "Registra entradas y salidas con fecha, motivo y existencia resultante.",
        )
        st.caption("El historial permanece únicamente durante la sesión actual.")

    st.warning(
        "Este historial todavía no usa base de datos. Inclúyelo en el respaldo general antes de cerrar la sesión."
    )

    items = _get_items()
    movements = _get_movements()

    if not items:
        st.info("No hay materiales registrados. Primero agrega o importa materiales desde Inventario.")
        return

    item_labels = {
        f"{item.get('name', 'Material')} · {item.get('item_id', '')}": item
        for item in items
    }

    st.subheader("Registrar movimiento")
    with st.form("tracked_inventory_movement_form", clear_on_submit=True):
        selected_label = st.selectbox("Material", tuple(item_labels.keys()))
        selected_item = item_labels[selected_label]

        form_columns = st.columns(3)
        with form_columns[0]:
            movement_type = st.selectbox("Tipo de movimiento", ("Entrada", "Salida"))
        with form_columns[1]:
            quantity = st.number_input(
                f"Cantidad en {selected_item.get('unit_name', 'unidad')}",
                min_value=0.01,
                value=1.0,
                step=1.0,
            )
        with form_columns[2]:
            reason = st.text_input(
                "Motivo",
                max_chars=120,
                placeholder="Ejemplo: compra, producción, ajuste o pérdida",
            )

        submitted = st.form_submit_button(
            "Registrar movimiento",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        cleaned_reason = reason.strip()
        available_quantity = float(selected_item.get("available_quantity", 0.0))

        if not cleaned_reason:
            st.error("Debes indicar el motivo del movimiento.")
        elif movement_type == "Salida" and float(quantity) > available_quantity:
            st.error("La salida no puede superar la existencia disponible.")
        else:
            updated_items, previous_quantity, resulting_quantity = _apply_movement(
                items,
                item_id=str(selected_item.get("item_id", "")),
                movement_type=movement_type,
                quantity=float(quantity),
            )
            movements.append(
                {
                    "movement_id": uuid4().hex[:10],
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "item_id": str(selected_item.get("item_id", "")),
                    "item_name": str(selected_item.get("name", "Material")),
                    "movement_type": movement_type,
                    "quantity": float(quantity),
                    "unit_name": str(selected_item.get("unit_name", "unidad")),
                    "reason": cleaned_reason,
                    "previous_quantity": previous_quantity,
                    "resulting_quantity": resulting_quantity,
                }
            )
            _save_items(updated_items)
            _save_movements(movements)
            st.success("Movimiento registrado y existencia actualizada.")
            st.rerun()

    st.divider()
    st.subheader("Resumen")
    entry_count = sum(1 for movement in movements if movement.get("movement_type") == "Entrada")
    exit_count = sum(1 for movement in movements if movement.get("movement_type") == "Salida")
    summary_columns = st.columns(3)
    summary_columns[0].metric("Movimientos registrados", str(len(movements)))
    summary_columns[1].metric("Entradas", str(entry_count))
    summary_columns[2].metric("Salidas", str(exit_count))

    if not movements:
        st.info("Todavía no hay movimientos registrados en esta sesión.")
        return

    st.subheader("Historial")
    for movement in reversed(movements):
        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {movement.get('item_name', 'Material')}")
                st.caption(
                    f"{movement.get('movement_type', '')} · ID {movement.get('movement_id', '')} · "
                    f"{movement.get('created_at_utc', '')}"
                )
            with title_columns[1]:
                if st.button(
                    "Eliminar registro",
                    key=f"delete_movement_{movement.get('movement_id', '')}",
                    use_container_width=True,
                    help="Elimina solo el registro histórico; no revierte la existencia.",
                ):
                    _save_movements(
                        [
                            item
                            for item in movements
                            if item.get("movement_id") != movement.get("movement_id")
                        ]
                    )
                    st.rerun()

            detail_columns = st.columns(3)
            detail_columns[0].metric(
                "Cantidad",
                f"{float(movement.get('quantity', 0.0)):,.2f} {movement.get('unit_name', 'unidad')}",
            )
            detail_columns[1].metric(
                "Existencia anterior",
                f"{float(movement.get('previous_quantity', 0.0)):,.2f}",
            )
            detail_columns[2].metric(
                "Existencia resultante",
                f"{float(movement.get('resulting_quantity', 0.0)):,.2f}",
            )

            render_info_card(
                "Motivo",
                str(movement.get("reason", "Sin motivo registrado")),
                "TRAZABILIDAD TEMPORAL",
            )

    st.info(
        "Eliminar un registro del historial no revierte automáticamente el movimiento aplicado al inventario."
    )
