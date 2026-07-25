"""Vista segura de movimientos manuales de Inventario.

Las entradas por compra se registran exclusivamente desde Recepción. Esta vista
conserva los movimientos operativos y ajustes sin modificar estructuras ni datos
existentes.
"""
from __future__ import annotations

import streamlit as st

from src import inventory_enterprise
from src.session_utils import read_list

MANUAL_MOVEMENTS = (
    "Salida",
    "Ajuste positivo",
    "Ajuste negativo",
    "Merma",
    "Devolución",
)
NEGATIVE_MOVEMENTS = {"Salida", "Ajuste negativo", "Merma"}


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render_inventory_movements_safe(rows: list[dict]) -> None:
    """Registra solo movimientos manuales que no correspondan a compras."""
    st.info(
        "Las compras y sus costos se reciben únicamente desde Recepción de mercancía. "
        "Aquí se registran salidas, devoluciones, mermas y ajustes autorizados."
    )

    active_rows = [row for row in rows if row.get("active", True)]
    if not active_rows:
        st.info("No hay artículos activos disponibles para registrar movimientos.")
        return

    labels = {
        (
            f"{row['name']} · {row.get('sku') or row.get('item_id')} · "
            f"existencia {_num(row.get('available_quantity')):,.2f} {row.get('unit_name', '')}"
        ): row
        for row in active_rows
    }

    with st.form("inventory_safe_manual_movement", clear_on_submit=True):
        selected = st.selectbox("Artículo", tuple(labels))
        movement_type = st.selectbox("Tipo de movimiento", MANUAL_MOVEMENTS)
        quantity = st.number_input("Cantidad", min_value=0.0001, value=1.0, step=1.0)
        reason = st.text_input("Motivo / referencia obligatoria")
        submitted = st.form_submit_button(
            "Registrar movimiento",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        item = labels[selected]
        stock = _num(item.get("available_quantity"))
        if not reason.strip():
            st.error("Debes indicar el motivo o documento de referencia.")
            return
        if movement_type in NEGATIVE_MOVEMENTS and quantity > stock:
            st.error("La cantidad supera la existencia disponible.")
            return

        inventory_enterprise._movement(
            item,
            movement_type,
            float(quantity),
            reason.strip(),
        )
        inventory_enterprise._save(rows)
        st.success("Movimiento registrado con trazabilidad.")
        st.rerun()

    history = list(reversed(read_list("inventory_movements")[-200:]))
    if not history:
        st.info("Todavía no hay movimientos registrados.")
        return

    st.markdown("#### Historial reciente")
    st.dataframe(
        [
            {
                "Fecha": row.get("created_at_utc", ""),
                "Movimiento": row.get("movement_type", ""),
                "Artículo": row.get("item_name", ""),
                "Cantidad": row.get("quantity", 0),
                "Anterior": row.get("previous_quantity", 0),
                "Resultante": row.get("resulting_quantity", 0),
                "Motivo / referencia": row.get("reason", ""),
                "Documento origen": row.get("purchase_id") or row.get("invoice_number") or row.get("receipt_id") or "—",
            }
            for row in history
        ],
        use_container_width=True,
        hide_index=True,
    )
