"""Integración visible de Catálogo, Compras, Recepción e Inventario.

Cada área tiene una responsabilidad única:
- Catálogo define el artículo.
- Compras registra la orden y sus condiciones económicas.
- Recepción confirma lo recibido y actualiza costo/stock.
- Inventario consulta y controla existencias.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src import app_shell, inventory_enterprise
from src.catalog_items import get_catalog_items, render_catalog_items
from src.components import render_page_header
from src.goods_receipt import accept_receipt
from src.session_utils import read_list, save_list

PURCHASES_KEY = "catalog_purchase_orders"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _purchase_rows() -> list[dict]:
    return [dict(row) for row in read_list(PURCHASES_KEY)]


def _save_purchase_rows(rows: list[dict]) -> None:
    save_list(PURCHASES_KEY, rows)


def render_purchases_from_catalog() -> None:
    render_page_header(
        "Compras",
        "Registra cómo se adquiere un artículo del Catálogo. Comprar no aumenta existencias hasta que la mercancía sea recibida.",
    )
    items = get_catalog_items(include_inactive=False)
    if not items:
        st.warning("Primero crea o migra artículos en Catálogo de artículos.")
        return

    labels = {
        f"{item.name} · {item.sku or item.item_id} · {item.inventory_unit}": item
        for item in items
    }
    tab_new, tab_orders = st.tabs(("Nueva orden", "Órdenes de compra"))

    with tab_new:
        with st.form("catalog_purchase_order_form", clear_on_submit=True):
            selected = st.selectbox("Artículo del Catálogo", tuple(labels))
            item = labels[selected]
            a, b, c = st.columns(3)
            supplier = a.text_input("Proveedor")
            quantity = b.number_input("Cantidad ordenada", min_value=0.0001, value=1.0, step=1.0)
            unit_price = c.number_input("Precio unitario", min_value=0.0, value=0.0, step=0.01, format="%.4f")
            a, b, c = st.columns(3)
            currency = a.selectbox("Moneda", ("USD", "VES", "EUR"))
            exchange_rate = b.number_input("Tasa usada", min_value=0.0001, value=1.0, step=0.01, format="%.4f")
            payment_status = c.selectbox("Estado del pago", ("Pendiente", "Parcial", "Pagada", "Vencida", "Anulada"))
            a, b = st.columns(2)
            shipping = a.number_input("Envío / flete total", min_value=0.0, value=0.0, step=0.01)
            tax = b.number_input("Impuestos totales", min_value=0.0, value=0.0, step=0.01)
            notes = st.text_area("Observaciones")
            submitted = st.form_submit_button("Crear orden de compra", type="primary", use_container_width=True)

        if submitted:
            if unit_price <= 0:
                st.error("El precio unitario debe ser mayor que cero.")
            else:
                rows = _purchase_rows()
                order_id = f"OC-{uuid4().hex[:8].upper()}"
                rows.append({
                    "purchase_id": order_id,
                    "catalog_item_id": item.item_id,
                    "catalog_sku": item.sku,
                    "item_name": item.name,
                    "unit_name": item.inventory_unit,
                    "supplier": supplier.strip(),
                    "ordered_quantity": float(quantity),
                    "received_quantity": 0.0,
                    "unit_price": float(unit_price),
                    "currency": currency,
                    "exchange_rate": float(exchange_rate),
                    "shipping_cost": float(shipping),
                    "tax_amount": float(tax),
                    "payment_status": payment_status,
                    "purchase_status": "Ordenada",
                    "notes": notes.strip(),
                    "created_at_utc": _now(),
                })
                _save_purchase_rows(rows)
                st.success(f"Orden {order_id} creada. Aún no modificó el inventario.")
                st.rerun()

    with tab_orders:
        rows = list(reversed(_purchase_rows()))
        if not rows:
            st.info("No hay órdenes registradas.")
        else:
            st.dataframe([
                {
                    "Orden": row.get("purchase_id"),
                    "Artículo": row.get("item_name"),
                    "Proveedor": row.get("supplier"),
                    "Ordenado": row.get("ordered_quantity"),
                    "Recibido": row.get("received_quantity", 0),
                    "Unidad": row.get("unit_name"),
                    "Precio unitario": row.get("unit_price"),
                    "Moneda": row.get("currency"),
                    "Compra": row.get("purchase_status"),
                    "Pago": row.get("payment_status"),
                }
                for row in rows
            ], use_container_width=True, hide_index=True)


def render_receiving_from_purchases() -> None:
    render_page_header(
        "Recepción de mercancía",
        "Confirma lo que realmente llegó. Solo aquí aumentan las existencias y se actualiza el costo promedio ponderado.",
    )
    rows = _purchase_rows()
    pending = [
        row for row in rows
        if row.get("purchase_status") not in {"Recibida", "Cerrada", "Cancelada"}
        and _num(row.get("received_quantity")) < _num(row.get("ordered_quantity"))
    ]
    if not pending:
        st.info("No hay órdenes pendientes de recepción.")
    else:
        labels = {
            f"{row.get('purchase_id')} · {row.get('item_name')} · pendiente {_num(row.get('ordered_quantity')) - _num(row.get('received_quantity')):,.2f} {row.get('unit_name', '')}": row
            for row in pending
        }
        with st.form("integrated_goods_receipt", clear_on_submit=True):
            selected = st.selectbox("Orden de compra", tuple(labels))
            order = labels[selected]
            pending_qty = _num(order.get("ordered_quantity")) - _num(order.get("received_quantity"))
            a, b, c = st.columns(3)
            accepted_qty = a.number_input("Cantidad aceptada", min_value=0.0001, max_value=float(pending_qty), value=float(min(pending_qty, 1.0)), step=1.0)
            lot = b.text_input("Lote")
            expiry = c.text_input("Vencimiento")
            notes = st.text_area("Observaciones de recepción")
            submitted = st.form_submit_button("Aceptar e ingresar al inventario", type="primary", use_container_width=True)

        if submitted:
            ordered_qty = _num(order.get("ordered_quantity"))
            already_received = _num(order.get("received_quantity"))
            rate = max(_num(order.get("exchange_rate"), 1.0), 0.0001)
            total_order_cost = (
                ordered_qty * _num(order.get("unit_price"))
                + _num(order.get("shipping_cost"))
                + _num(order.get("tax_amount"))
            ) / rate
            landed_unit_cost = total_order_cost / max(ordered_qty, 0.0001)
            receipt_id = f"REC-{uuid4().hex[:8].upper()}"
            result = accept_receipt(
                receipt_id=receipt_id,
                catalog_item_id=str(order.get("catalog_item_id")),
                accepted_qty=float(accepted_qty),
                unit_cost=landed_unit_cost,
                ordered_qty=ordered_qty,
                already_received=already_received,
                supplier_id=str(order.get("supplier", "")),
                purchase_id=str(order.get("purchase_id", "")),
                lot=lot.strip(),
                expiry=expiry.strip(),
                notes=notes.strip(),
            )
            if result.get("ok"):
                updated = []
                for row in rows:
                    current = dict(row)
                    if current.get("purchase_id") == order.get("purchase_id"):
                        received = already_received + float(accepted_qty)
                        current["received_quantity"] = received
                        current["purchase_status"] = "Recibida" if received >= ordered_qty else "Parcialmente recibida"
                        current["updated_at_utc"] = _now()
                    updated.append(current)
                _save_purchase_rows(updated)
                st.success(f"Recepción {receipt_id} procesada. Inventario y costo promedio actualizados.")
                st.rerun()
            else:
                for error in result.get("errors", ["No se pudo procesar la recepción."]):
                    st.error(error)

    history = list(reversed(read_list("goods_receipts")[-200:]))
    if history:
        st.markdown("#### Historial de recepciones")
        st.dataframe(history, use_container_width=True, hide_index=True)


def render_inventory_stock_only() -> None:
    render_page_header(
        "Inventario",
        "Consulta y controla existencias. La definición del artículo está en Catálogo; los costos de compra, en Compras; y las entradas compradas, en Recepción.",
    )
    rows = inventory_enterprise._items()
    tabs = st.tabs(("Panel", "Existencias", "Movimientos", "Reservas", "Conteo físico", "Reposición"))
    with tabs[0]:
        inventory_enterprise._dashboard(rows)
    with tabs[1]:
        inventory_enterprise._catalog(rows)
    with tabs[2]:
        inventory_enterprise._movements(rows)
    with tabs[3]:
        inventory_enterprise._reservations(rows)
    with tabs[4]:
        inventory_enterprise._counts(rows)
    with tabs[5]:
        inventory_enterprise._replenishment(rows)
    st.info("Las entradas provenientes de compras deben registrarse en Recepción. Los ajustes manuales permanecen disponibles en Movimientos y Conteo físico.")


def activate_supply_chain_integration() -> None:
    app_shell.FUNCTIONAL_MODULES["Catálogo de artículos"] = render_catalog_items
    app_shell.FUNCTIONAL_MODULES["Compras"] = render_purchases_from_catalog
    app_shell.FUNCTIONAL_MODULES["Recepción de mercancía"] = render_receiving_from_purchases
    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_stock_only
