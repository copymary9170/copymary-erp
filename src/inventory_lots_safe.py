"""Trazabilidad visual de lotes y vencimientos para Inventario.

Extiende la vista de existencias sin modificar costos, movimientos ni datos guardados.
"""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from src.inventory_stock_view import render_inventory_stock_table


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _expiry(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _expiry_status(expiry: date | None, today: date) -> tuple[str, int | None]:
    if expiry is None:
        return "Sin vencimiento", None
    days = (expiry - today).days
    if days < 0:
        return "Vencido", days
    if days <= 30:
        return "Vence en 30 días", days
    if days <= 90:
        return "Vence en 90 días", days
    return "Vigente", days


def render_inventory_stock_with_lots(rows: list[dict]) -> None:
    """Conserva Existencias y añade control visual de lotes y vencimientos."""
    render_inventory_stock_table(rows)

    st.divider()
    st.markdown("### Trazabilidad de lotes y vencimientos")
    st.caption(
        "Esta sección solo analiza la información ya registrada. No cambia existencias, "
        "costos, movimientos ni fechas."
    )

    today = date.today()
    traced: list[dict] = []
    for row in rows:
        if not row.get("active", True):
            continue
        lot = str(row.get("lot") or "").strip()
        expiry = _expiry(row.get("expiry_date") or row.get("expiry"))
        if not lot and expiry is None:
            continue
        status, days = _expiry_status(expiry, today)
        quantity = _num(row.get("available_quantity", row.get("stock", 0.0)))
        unit_cost = _num(row.get("average_cost", row.get("unit_cost", 0.0)))
        traced.append({
            "SKU": row.get("sku") or row.get("item_id"),
            "Artículo": row.get("name") or row.get("material_name") or "Material",
            "Lote": lot or "Sin lote",
            "Vencimiento": expiry.isoformat() if expiry else "—",
            "Días restantes": days if days is not None else "—",
            "Estado": status,
            "Existencia física": round(quantity, 4),
            "Unidad": row.get("unit_name") or row.get("unit") or "unidad",
            "Ubicación": row.get("location") or "Almacén principal",
            "Valor del lote": round(quantity * unit_cost, 2),
        })

    if not traced:
        st.info("No hay artículos activos con lote o vencimiento registrado.")
        return

    status_filter = st.selectbox(
        "Filtrar vencimientos",
        ("Todos", "Vencido", "Vence en 30 días", "Vence en 90 días", "Vigente", "Sin vencimiento"),
        key="inventory_lot_expiry_status",
    )
    filtered = [row for row in traced if status_filter == "Todos" or row["Estado"] == status_filter]

    metrics = st.columns(5)
    metrics[0].metric("Lotes registrados", len({row["Lote"] for row in traced if row["Lote"] != "Sin lote"}))
    metrics[1].metric("Vencidos", sum(row["Estado"] == "Vencido" for row in traced))
    metrics[2].metric("≤ 30 días", sum(row["Estado"] == "Vence en 30 días" for row in traced))
    metrics[3].metric("≤ 90 días", sum(row["Estado"] == "Vence en 90 días" for row in traced))
    metrics[4].metric("Sin vencimiento", sum(row["Estado"] == "Sin vencimiento" for row in traced))

    st.dataframe(
        sorted(filtered, key=lambda row: (row["Días restantes"] == "—", row["Días restantes"] if row["Días restantes"] != "—" else 10**9)),
        use_container_width=True,
        hide_index=True,
    )

    urgent = [row for row in traced if row["Estado"] in {"Vencido", "Vence en 30 días"}]
    if urgent:
        st.warning(
            "Hay existencias vencidas o próximas a vencer. Revisa físicamente el lote y define "
            "la acción operativa correspondiente antes de utilizarlo."
        )
