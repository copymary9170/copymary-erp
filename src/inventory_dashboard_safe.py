"""Panel operativo de Inventario, fase 3.

Solo lee registros existentes y mejora la presentación. No modifica stock, costos,
reservas, movimientos ni estructura de datos.
"""
from __future__ import annotations

import streamlit as st

from src.session_utils import read_list


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _reserved_by_item() -> dict[str, float]:
    reserved: dict[str, float] = {}
    for row in read_list("inventory_reservations"):
        if row.get("status") != "Activa":
            continue
        item_id = str(row.get("item_id") or "")
        reserved[item_id] = reserved.get(item_id, 0.0) + _num(row.get("quantity"))
    return reserved


def render_inventory_dashboard(rows: list[dict]) -> None:
    """Muestra indicadores seguros derivados de los datos actuales."""
    active = [row for row in rows if row.get("active", True)]
    reserved_map = _reserved_by_item()

    physical_total = sum(_num(row.get("available_quantity")) for row in active)
    reserved_total = sum(
        min(reserved_map.get(str(row.get("item_id")), 0.0), _num(row.get("available_quantity")))
        for row in active
    )
    available_total = max(physical_total - reserved_total, 0.0)
    inventory_value = sum(
        max(_num(row.get("available_quantity")) - reserved_map.get(str(row.get("item_id")), 0.0), 0.0)
        * _num(row.get("unit_cost"))
        for row in active
    )

    low_stock = []
    out_of_stock = []
    without_cost = []
    without_location = []
    overstock = []

    for row in active:
        physical = _num(row.get("available_quantity"))
        reserved = reserved_map.get(str(row.get("item_id")), 0.0)
        available = max(physical - reserved, 0.0)
        minimum = _num(row.get("minimum_stock"))
        maximum = _num(row.get("maximum_stock"))

        if available <= 0:
            out_of_stock.append(row)
        elif minimum > 0 and available <= minimum:
            low_stock.append(row)
        if _num(row.get("unit_cost")) <= 0:
            without_cost.append(row)
        if not str(row.get("location") or "").strip():
            without_location.append(row)
        if maximum > 0 and physical > maximum:
            overstock.append(row)

    metrics = st.columns(6)
    metrics[0].metric("Artículos activos", len(active))
    metrics[1].metric("Existencia física", f"{physical_total:,.2f}")
    metrics[2].metric("Reservado", f"{reserved_total:,.2f}")
    metrics[3].metric("Disponible", f"{available_total:,.2f}")
    metrics[4].metric("Valor disponible", f"${inventory_value:,.2f}")
    metrics[5].metric("Movimientos", len(read_list("inventory_movements")))

    alerts = st.columns(5)
    alerts[0].metric("Stock bajo", len(low_stock))
    alerts[1].metric("Agotados", len(out_of_stock))
    alerts[2].metric("Sin costo", len(without_cost))
    alerts[3].metric("Sin ubicación", len(without_location))
    alerts[4].metric("Sobre máximo", len(overstock))

    priority = []
    for row in active:
        physical = _num(row.get("available_quantity"))
        reserved = reserved_map.get(str(row.get("item_id")), 0.0)
        available = max(physical - reserved, 0.0)
        minimum = _num(row.get("minimum_stock"))
        maximum = _num(row.get("maximum_stock"))
        if available <= 0 or (minimum > 0 and available <= minimum):
            target = maximum if maximum > minimum else minimum * 2
            priority.append({
                "SKU": row.get("sku") or row.get("item_id"),
                "Artículo": row.get("name"),
                "Físico": round(physical, 2),
                "Reservado": round(reserved, 2),
                "Disponible": round(available, 2),
                "Mínimo": round(minimum, 2),
                "Sugerido": round(max(target - available, 0.0), 2),
                "Unidad": row.get("unit_name"),
            })

    if priority:
        st.markdown("#### Atención prioritaria")
        st.dataframe(priority, use_container_width=True, hide_index=True)
    else:
        st.success("No hay artículos agotados ni por debajo del mínimo disponible.")

    categories: dict[str, float] = {}
    for row in active:
        physical = _num(row.get("available_quantity"))
        reserved = reserved_map.get(str(row.get("item_id")), 0.0)
        available = max(physical - reserved, 0.0)
        category = str(row.get("category") or "Otro")
        categories[category] = categories.get(category, 0.0) + available * _num(row.get("unit_cost"))

    if categories:
        st.markdown("#### Valor disponible por categoría")
        st.dataframe(
            [
                {"Categoría": category, "Valor disponible ($)": round(value, 2)}
                for category, value in sorted(categories.items(), key=lambda item: item[1], reverse=True)
            ],
            use_container_width=True,
            hide_index=True,
        )

    if without_cost or without_location or overstock:
        with st.expander("Revisiones de calidad de datos"):
            st.write(f"Artículos sin costo promedio: **{len(without_cost)}**")
            st.write(f"Artículos sin ubicación: **{len(without_location)}**")
            st.write(f"Artículos por encima del máximo: **{len(overstock)}**")
