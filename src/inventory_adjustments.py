"""Ajustes manuales y conteos físicos de inventario."""


from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.session_utils import now_iso as _now, read_list as _rows


def render_inventory_adjustments() -> None:
    with st.container(border=True):
        render_page_header(
            "Ajustes de inventario",
            "Registra entradas, salidas y conteos físicos con trazabilidad completa.",
        )
        st.caption("Cada corrección crea un movimiento; el historial original no se elimina.")

    inventory = _rows("inventory_registry")
    movements = _rows("inventory_movements")

    if not inventory:
        st.info("Registra materiales en Inventario antes de realizar ajustes.")
        return

    labels = {
        f"{item.get('name', 'Material')} · {item.get('available_quantity', 0)} {item.get('unit_name', 'unidad')} · {item.get('item_id', '')}": item
        for item in inventory
    }

    with st.form("inventory_adjustment_form", clear_on_submit=True):
        selected = labels[st.selectbox("Material", tuple(labels.keys()))]
        mode = st.selectbox("Tipo de ajuste", ("Entrada", "Salida", "Conteo físico"))
        current_quantity = float(selected.get("available_quantity", 0.0))
        if mode == "Conteo físico":
            quantity = st.number_input(
                "Existencia contada",
                min_value=0.0,
                value=current_quantity,
                step=1.0,
            )
        else:
            quantity = st.number_input("Cantidad", min_value=0.01, value=1.0, step=1.0)
        reason = st.text_input("Motivo", max_chars=220)
        reference = st.text_input("Referencia opcional", max_chars=80)
        confirm = st.checkbox("Confirmo que la cantidad fue revisada.")
        submitted = st.form_submit_button(
            "Aplicar ajuste",
            type="primary",
            use_container_width=True,
            disabled=not confirm,
        )

    if submitted:
        item_id = str(selected.get("item_id", ""))
        previous = float(selected.get("available_quantity", 0.0))
        if mode == "Entrada":
            resulting = previous + float(quantity)
            movement_type = "Entrada"
            moved = float(quantity)
        elif mode == "Salida":
            if float(quantity) > previous:
                st.error("La salida no puede superar la existencia disponible.")
                st.stop()
            resulting = previous - float(quantity)
            movement_type = "Salida"
            moved = float(quantity)
        else:
            resulting = float(quantity)
            difference = resulting - previous
            movement_type = "Entrada" if difference >= 0 else "Salida"
            moved = abs(difference)
            if moved <= 0:
                st.info("El conteo coincide con la existencia registrada; no se creó ningún movimiento.")
                st.stop()

        updated_inventory: list[dict] = []
        for item in inventory:
            current = dict(item)
            if str(item.get("item_id", "")) == item_id:
                current["available_quantity"] = resulting
            updated_inventory.append(current)

        movement_id = uuid4().hex[:10]
        movements.append(
            {
                "movement_id": movement_id,
                "created_at_utc": _now(),
                "item_id": item_id,
                "item_name": str(selected.get("name", "Material")),
                "movement_type": movement_type,
                "quantity": moved,
                "unit_name": str(selected.get("unit_name", "unidad")),
                "reason": reason.strip() or f"Ajuste manual: {mode}",
                "reference": reference.strip() or f"AJ-{movement_id}",
                "adjustment_mode": mode,
                "previous_quantity": previous,
                "resulting_quantity": resulting,
            }
        )
        st.session_state["inventory_registry"] = updated_inventory
        st.session_state["inventory_movements"] = movements
        st.success("Ajuste aplicado y movimiento registrado.")
        st.rerun()

    st.divider()
    st.subheader("Ajustes recientes")
    adjustments = [item for item in movements if item.get("adjustment_mode")]
    if not adjustments:
        st.info("Todavía no hay ajustes manuales registrados.")
    for item in reversed(adjustments[-20:]):
        with st.container(border=True):
            columns = st.columns(4)
            columns[0].metric("Material", str(item.get("item_name", "")))
            columns[1].metric("Tipo", str(item.get("adjustment_mode", "")))
            columns[2].metric("Anterior", f"{float(item.get('previous_quantity', 0.0)):,.2f}")
            columns[3].metric("Resultante", f"{float(item.get('resulting_quantity', 0.0)):,.2f}")
            st.caption(
                f"{item.get('created_at_utc', '')} · {item.get('reason', '')} · Ref. {item.get('reference', '')}"
            )

    render_info_card(
        "Control de existencia",
        "Usa Conteo físico cuando la cantidad real no coincide con el sistema; la diferencia quedará documentada.",
        "TRAZABILIDAD DE INVENTARIO",
    )
