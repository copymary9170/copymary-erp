"""Vista segura de existencias para Inventario.

Esta primera fase solo cambia la presentación. No modifica movimientos, costos,
reservas ni registros existentes.
"""
from __future__ import annotations

import streamlit as st

from src.inventory_action_permissions import can_inventory_action
from src.session_utils import read_list


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _reserved_for(item_id: str, reservations: list[dict]) -> float:
    return sum(
        _num(row.get("quantity"))
        for row in reservations
        if str(row.get("item_id")) == str(item_id) and row.get("status") == "Activa"
    )


def render_inventory_stock_table(rows: list[dict]) -> None:
    """Muestra existencias sin mezclar proveedor, moneda ni método de pago."""
    reservations = read_list("inventory_reservations")
    can_view_costs = can_inventory_action("cost_view")

    a, b, c = st.columns([2, 1, 1])
    query = a.text_input("Buscar por nombre, SKU, lote o ubicación", key="inventory_stock_query")
    categories = sorted({str(row.get("category") or "Otro") for row in rows})
    category = b.selectbox("Categoría", ("Todas", *categories), key="inventory_stock_category")
    status = c.selectbox(
        "Estado",
        ("Todos", "Disponible", "Stock bajo", "Agotado", "Inactivo"),
        key="inventory_stock_status",
    )

    if not can_view_costs:
        st.info("Tu rol puede consultar existencias, pero no tiene permiso para visualizar costos ni valores monetarios.")

    table: list[dict] = []
    for row in rows:
        item_id = str(row.get("item_id") or row.get("catalog_item_id") or "")
        physical = _num(row.get("available_quantity", row.get("stock", row.get("quantity", 0.0))))
        reserved = _reserved_for(item_id, reservations)
        available = max(physical - reserved, 0.0)
        minimum = _num(row.get("minimum_stock"))
        maximum = _num(row.get("maximum_stock"))
        active = bool(row.get("active", True))
        current = "Inactivo" if not active else "Agotado" if available <= 0 else "Stock bajo" if minimum > 0 and available <= minimum else "Disponible"

        haystack = " ".join(
            str(row.get(field, ""))
            for field in ("name", "material_name", "sku", "item_id", "lot", "location")
        ).casefold()
        if query and query.casefold() not in haystack:
            continue
        if category != "Todas" and str(row.get("category") or "Otro") != category:
            continue
        if status != "Todos" and current != status:
            continue

        unit_cost = _num(row.get("average_cost", row.get("unit_cost", 0.0)))
        item_row = {
            "SKU": row.get("sku") or item_id,
            "Artículo": row.get("name") or row.get("material_name") or "Material",
            "Categoría": row.get("category") or "Otro",
            "Ubicación": row.get("location") or "Almacén principal",
            "Existencia física": round(physical, 4),
            "Reservado": round(reserved, 4),
            "Disponible": round(available, 4),
            "Unidad": row.get("unit_name") or row.get("unit") or "unidad",
            "Mínimo": round(minimum, 4),
            "Máximo": round(maximum, 4),
            "Lote": row.get("lot") or "",
            "Vencimiento": row.get("expiry_date") or row.get("expiry") or "",
            "Estado": current,
        }
        if can_view_costs:
            item_row["Costo promedio"] = round(unit_cost, 4)
            item_row["Valor disponible"] = round(available * unit_cost, 2)
        table.append(item_row)

    if not table:
        st.info("No hay artículos que coincidan con los filtros.")
        return

    st.dataframe(table, use_container_width=True, hide_index=True)
    metrics = st.columns(4 if can_view_costs else 3)
    metrics[0].metric("Resultados", len(table))
    metrics[1].metric("Existencia física", f"{sum(_num(row['Existencia física']) for row in table):,.2f}")
    metrics[2].metric("Reservado", f"{sum(_num(row['Reservado']) for row in table):,.2f}")
    if can_view_costs:
        metrics[3].metric("Valor disponible", f"${sum(_num(row['Valor disponible']) for row in table):,.2f}")
