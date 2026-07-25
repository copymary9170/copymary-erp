"""Vista segura de reposición para Inventario.

Calcula sugerencias usando existencia física, reservas activas y compras pendientes.
No crea órdenes ni modifica datos.
"""
from __future__ import annotations

import streamlit as st

from src.session_utils import read_list


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _reserved_map() -> dict[str, float]:
    result: dict[str, float] = {}
    for row in read_list("inventory_reservations"):
        if row.get("status") != "Activa":
            continue
        item_id = str(row.get("item_id") or "")
        result[item_id] = result.get(item_id, 0.0) + _num(row.get("quantity"))
    return result


def _pending_purchase_map() -> dict[str, float]:
    result: dict[str, float] = {}
    for row in read_list("catalog_purchase_orders"):
        if row.get("purchase_status") in {"Recibida", "Cerrada", "Cancelada"}:
            continue
        ordered = _num(row.get("ordered_quantity"))
        received = _num(row.get("received_quantity"))
        pending = max(ordered - received, 0.0)
        if pending <= 0:
            continue
        keys = {
            str(row.get("catalog_item_id") or ""),
            str(row.get("catalog_sku") or ""),
        }
        for key in keys:
            if key:
                result[key] = result.get(key, 0.0) + pending
    return result


def render_inventory_replenishment_safe(rows: list[dict]) -> None:
    """Muestra necesidades de reposición sin crear compras automáticamente."""
    st.info(
        "La sugerencia considera reservas activas y órdenes de compra pendientes. "
        "Inventario no crea compras automáticamente."
    )

    reserved_map = _reserved_map()
    pending_map = _pending_purchase_map()
    candidates: list[dict] = []

    for row in rows:
        if not row.get("active", True):
            continue
        item_id = str(row.get("item_id") or row.get("catalog_item_id") or "")
        sku = str(row.get("sku") or "")
        physical = _num(row.get("available_quantity"))
        reserved = reserved_map.get(item_id, 0.0)
        available = max(physical - reserved, 0.0)
        pending = max(pending_map.get(item_id, 0.0), pending_map.get(sku, 0.0))
        projected = available + pending
        minimum = _num(row.get("minimum_stock"))
        maximum = _num(row.get("maximum_stock"))

        if minimum <= 0 or projected > minimum:
            continue

        target = maximum if maximum > minimum else minimum * 2
        suggested = max(target - projected, 0.0)
        unit_cost = _num(row.get("average_cost", row.get("unit_cost")))
        candidates.append({
            "Prioridad": "Crítica" if available <= 0 and pending <= 0 else "Alta" if available <= minimum else "Cubierta parcialmente",
            "SKU": sku or item_id,
            "Artículo": row.get("name") or row.get("material_name") or "Material",
            "Físico": round(physical, 2),
            "Reservado": round(reserved, 2),
            "Disponible": round(available, 2),
            "Compra pendiente": round(pending, 2),
            "Proyectado": round(projected, 2),
            "Mínimo": round(minimum, 2),
            "Máximo": round(maximum, 2),
            "Sugerido": round(suggested, 2),
            "Unidad": row.get("unit_name") or row.get("unit") or "unidad",
            "Costo estimado": round(suggested * unit_cost, 2),
        })

    if not candidates:
        st.success("No hay artículos que requieran reposición después de considerar reservas y compras pendientes.")
        return

    order = {"Crítica": 0, "Alta": 1, "Cubierta parcialmente": 2}
    candidates.sort(key=lambda row: (order.get(str(row["Prioridad"]), 9), str(row["Artículo"])))

    metrics = st.columns(4)
    metrics[0].metric("Artículos a revisar", len(candidates))
    metrics[1].metric("Críticos", sum(1 for row in candidates if row["Prioridad"] == "Crítica"))
    metrics[2].metric("Unidades sugeridas", f"{sum(_num(row['Sugerido']) for row in candidates):,.2f}")
    metrics[3].metric("Costo estimado", f"${sum(_num(row['Costo estimado']) for row in candidates):,.2f}")

    st.dataframe(candidates, use_container_width=True, hide_index=True)
    st.caption(
        "La columna Compra pendiente solo informa órdenes todavía no recibidas. "
        "La orden debe crearse o modificarse desde Compras."
    )
