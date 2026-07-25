"""Conteo físico seguro de Inventario, fase 4.

El conteo calcula diferencias primero y solo crea el ajuste cuando la persona
confirma expresamente. No modifica movimientos históricos ni estructuras actuales.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src import inventory_enterprise
from src.session_utils import read_list, save_list

COUNTS_KEY = "inventory_count_sessions"


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_inventory_counts_safe(rows: list[dict]) -> None:
    """Registra conteos con revisión y confirmación previa al ajuste."""
    st.info(
        "El conteo no cambia la existencia de inmediato. Primero se calcula la "
        "diferencia y luego debes confirmar expresamente el ajuste."
    )

    active = [row for row in rows if row.get("active", True)]
    if not active:
        st.info("No hay artículos activos para contar.")
        return

    labels = {
        (
            f"{row.get('name', 'Artículo')} · {row.get('sku') or row.get('item_id')} · "
            f"sistema {_num(row.get('available_quantity')):,.2f} {row.get('unit_name', '')}"
        ): row
        for row in active
    }

    selected = st.selectbox("Artículo a contar", tuple(labels), key="safe_count_item")
    item = labels[selected]
    system_quantity = _num(item.get("available_quantity"))

    counted_quantity = st.number_input(
        "Cantidad física contada",
        min_value=0.0,
        value=float(system_quantity),
        step=1.0,
        key="safe_count_quantity",
    )
    reference = st.text_input(
        "Responsable / referencia del conteo",
        key="safe_count_reference",
    )

    difference = float(counted_quantity) - system_quantity
    preview = st.columns(4)
    preview[0].metric("Cantidad del sistema", f"{system_quantity:,.2f}")
    preview[1].metric("Cantidad contada", f"{counted_quantity:,.2f}")
    preview[2].metric("Diferencia", f"{difference:+,.2f}")
    preview[3].metric(
        "Resultado propuesto",
        f"{counted_quantity:,.2f}",
    )

    if difference == 0:
        st.success("El conteo coincide con la existencia del sistema. No se requiere ajuste.")
    elif difference > 0:
        st.warning(f"Se propone un ajuste positivo de {difference:,.2f} unidades.")
    else:
        st.warning(f"Se propone un ajuste negativo de {abs(difference):,.2f} unidades.")

    confirm = st.checkbox(
        "Confirmo que revisé la diferencia y autorizo aplicar el ajuste",
        key="safe_count_confirm",
        disabled=difference == 0,
    )
    apply_adjustment = st.button(
        "Cerrar conteo y aplicar ajuste",
        type="primary",
        use_container_width=True,
        disabled=difference == 0 or not confirm,
    )

    if apply_adjustment:
        if not reference.strip():
            st.error("Debes indicar responsable o referencia antes de aplicar el ajuste.")
            return

        movement_type = "Ajuste positivo" if difference > 0 else "Ajuste negativo"
        quantity = abs(difference)
        count_id = f"CON-{uuid4().hex[:8].upper()}"
        reason = f"Conteo físico {count_id} · {reference.strip()}"

        inventory_enterprise._movement(
            item,
            movement_type,
            quantity,
            reason,
        )
        inventory_enterprise._save(rows)

        sessions = read_list(COUNTS_KEY)
        sessions.append({
            "count_id": count_id,
            "created_at_utc": _now(),
            "item_id": item.get("item_id"),
            "sku": item.get("sku"),
            "item_name": item.get("name"),
            "system_quantity": system_quantity,
            "counted_quantity": float(counted_quantity),
            "difference": difference,
            "movement_type": movement_type,
            "reference": reference.strip(),
            "status": "Aplicado",
        })
        save_list(COUNTS_KEY, sessions)
        st.success(f"Conteo {count_id} aplicado y documentado.")
        st.rerun()

    history = list(reversed(read_list(COUNTS_KEY)[-100:]))
    if history:
        st.markdown("#### Historial de conteos confirmados")
        st.dataframe(
            [
                {
                    "Conteo": row.get("count_id", ""),
                    "Fecha": row.get("created_at_utc", ""),
                    "Artículo": row.get("item_name", ""),
                    "Sistema": row.get("system_quantity", 0),
                    "Contado": row.get("counted_quantity", 0),
                    "Diferencia": row.get("difference", 0),
                    "Responsable / referencia": row.get("reference", ""),
                    "Estado": row.get("status", ""),
                }
                for row in history
            ],
            use_container_width=True,
            hide_index=True,
        )
