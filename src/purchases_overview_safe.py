"""Mejora segura y visual del módulo Compras.

Añade un resumen operativo, filtros y detalle calculado sin modificar órdenes,
recepciones, costos ni existencias.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from src.session_utils import read_list


PURCHASES_KEY = "catalog_purchase_orders"


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pending(row: dict) -> float:
    return max(_num(row.get("ordered_quantity")) - _num(row.get("received_quantity")), 0.0)


def _status(row: dict) -> str:
    explicit = str(row.get("purchase_status") or "").strip()
    if explicit:
        return explicit
    ordered = _num(row.get("ordered_quantity"))
    received = _num(row.get("received_quantity"))
    if received <= 0:
        return "Ordenada"
    if received < ordered:
        return "Parcialmente recibida"
    return "Recibida"


def _base_total(row: dict) -> float:
    return _num(row.get("ordered_quantity")) * _num(row.get("unit_price"))


def _grand_total(row: dict) -> float:
    return _base_total(row) + _num(row.get("shipping_cost")) + _num(row.get("tax_amount"))


def _base_currency_total(row: dict) -> float:
    rate = max(_num(row.get("exchange_rate"), 1.0), 0.0001)
    return _grand_total(row) / rate


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _rows() -> list[dict]:
    return [dict(row) for row in read_list(PURCHASES_KEY)]


def render_purchases_overview_safe() -> None:
    """Muestra control operativo de compras sin alterar sus registros."""
    rows = _rows()

    st.markdown("### Resumen operativo de compras")
    st.caption(
        "Vista de control y seguimiento. Los valores se calculan desde las órdenes actuales; "
        "no crea recepciones ni modifica inventario."
    )

    if not rows:
        st.info("No hay órdenes de compra para analizar.")
        return

    statuses = sorted({_status(row) for row in rows})
    suppliers = sorted({str(row.get("supplier") or "Sin proveedor") for row in rows})
    currencies = sorted({str(row.get("currency") or "Sin moneda") for row in rows})

    a, b, c, d = st.columns([2, 1, 1, 1])
    query = a.text_input(
        "Buscar orden, artículo, SKU o proveedor",
        key="purchases_overview_query",
    )
    selected_status = b.selectbox(
        "Estado",
        ["Todos", *statuses],
        key="purchases_overview_status",
    )
    selected_supplier = c.selectbox(
        "Proveedor",
        ["Todos", *suppliers],
        key="purchases_overview_supplier",
    )
    selected_currency = d.selectbox(
        "Moneda",
        ["Todas", *currencies],
        key="purchases_overview_currency",
    )

    e, f = st.columns(2)
    start_date = e.date_input("Desde", value=None, key="purchases_overview_from")
    end_date = f.date_input("Hasta", value=None, key="purchases_overview_to")

    filtered: list[dict] = []
    for row in rows:
        status = _status(row)
        supplier = str(row.get("supplier") or "Sin proveedor")
        currency = str(row.get("currency") or "Sin moneda")
        haystack = " ".join(
            str(row.get(field) or "")
            for field in ("purchase_id", "item_name", "catalog_sku", "supplier", "notes")
        ).casefold()
        created = _parse_date(row.get("created_at_utc"))

        if query and query.casefold() not in haystack:
            continue
        if selected_status != "Todos" and status != selected_status:
            continue
        if selected_supplier != "Todos" and supplier != selected_supplier:
            continue
        if selected_currency != "Todas" and currency != selected_currency:
            continue
        if start_date and created and created < start_date:
            continue
        if end_date and created and created > end_date:
            continue
        filtered.append(row)

    pending_orders = [row for row in filtered if _pending(row) > 0 and _status(row) not in {"Cancelada", "Cerrada"}]
    partial_orders = [row for row in filtered if _status(row) == "Parcialmente recibida"]
    unpaid_orders = [row for row in filtered if str(row.get("payment_status") or "") in {"Pendiente", "Parcial", "Vencida"}]

    metrics = st.columns(6)
    metrics[0].metric("Órdenes", len(filtered))
    metrics[1].metric("Pendientes de recibir", len(pending_orders))
    metrics[2].metric("Recepción parcial", len(partial_orders))
    metrics[3].metric("Pagos pendientes", len(unpaid_orders))
    metrics[4].metric("Unidades pendientes", f"{sum(_pending(row) for row in pending_orders):,.2f}")
    metrics[5].metric("Proveedores", len({str(row.get('supplier') or 'Sin proveedor') for row in filtered}))

    table = []
    for row in sorted(filtered, key=lambda item: str(item.get("created_at_utc") or ""), reverse=True):
        ordered = _num(row.get("ordered_quantity"))
        received = _num(row.get("received_quantity"))
        table.append({
            "Fecha": str(row.get("created_at_utc") or "")[:10],
            "Orden": row.get("purchase_id") or "",
            "Artículo": row.get("item_name") or "",
            "SKU": row.get("catalog_sku") or "",
            "Proveedor": row.get("supplier") or "Sin proveedor",
            "Estado": _status(row),
            "Pago": row.get("payment_status") or "",
            "Ordenado": round(ordered, 4),
            "Recibido": round(received, 4),
            "Pendiente": round(max(ordered - received, 0.0), 4),
            "Unidad": row.get("unit_name") or "",
            "Precio unitario": round(_num(row.get("unit_price")), 4),
            "Moneda": row.get("currency") or "",
            "Tasa": round(_num(row.get("exchange_rate"), 1.0), 4),
            "Subtotal": round(_base_total(row), 2),
            "Flete": round(_num(row.get("shipping_cost")), 2),
            "Impuestos": round(_num(row.get("tax_amount")), 2),
            "Total orden": round(_grand_total(row), 2),
            "Total base": round(_base_currency_total(row), 2),
            "Observaciones": row.get("notes") or "",
        })

    if not table:
        st.info("No hay órdenes que coincidan con los filtros.")
        return

    st.dataframe(table, use_container_width=True, hide_index=True)

    if pending_orders:
        st.warning(
            "Hay órdenes pendientes de recepción. La mercancía debe confirmarse desde "
            "Recepción de mercancía para actualizar existencias y costo promedio."
        )

    st.caption(
        "Total base = (cantidad × precio + flete + impuestos) ÷ tasa registrada. "
        "Esta vista no recalcula ni modifica el costo promedio del inventario."
    )
