"""Panel ejecutivo seguro para la pantalla de Inicio.

Esta fase solo consulta datos ya presentes en ``st.session_state``. No crea,
modifica ni elimina registros y conserva los módulos operativos existentes.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

from src import auth
from src.session_utils import read_list


_NAVIGATION_TARGETS: dict[str, tuple[str, str]] = {
    "Nueva venta": ("Comercial y CRM", "Ventas y pedidos"),
    "Nueva compra": ("Compras y abastecimiento", "Compras"),
    "Recibir mercancía": ("Compras y abastecimiento", "Recepción de mercancía"),
    "Crear artículo": ("Inventario y almacén", "Catálogo de artículos"),
    "Nueva cotización": ("Comercial y CRM", "Cotizaciones"),
    "Registrar gasto": ("Finanzas y tesorería", "Gastos y presupuesto"),
    "Abrir caja": ("Finanzas y tesorería", "Caja"),
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _active_sales() -> list[dict]:
    return [
        row for row in read_list("sales_registry")
        if str(row.get("order_status", "Pendiente")).strip().casefold()
        not in {"cancelado", "cancelada", "anulado", "anulada"}
    ]


def _sales_total_today(rows: list[dict]) -> float:
    today = date.today()
    return sum(
        _num(row.get("total", row.get("grand_total", row.get("amount", 0.0))))
        for row in rows
        if _date_value(row.get("created_at_utc") or row.get("created_at") or row.get("date")) == today
    )


def _pending_purchase_rows() -> list[dict]:
    rows = read_list("catalog_purchase_orders")
    return [
        row for row in rows
        if str(row.get("purchase_status", "Ordenada"))
        not in {"Recibida", "Cerrada", "Cancelada"}
        and _num(row.get("received_quantity")) < _num(row.get("ordered_quantity"))
    ]


def _inventory_alerts() -> tuple[int, int]:
    low = 0
    out = 0
    reservations = read_list("inventory_reservations")
    reserved_by_item: dict[str, float] = {}
    for reservation in reservations:
        if reservation.get("status") != "Activa":
            continue
        item_id = str(reservation.get("item_id") or "")
        reserved_by_item[item_id] = reserved_by_item.get(item_id, 0.0) + _num(reservation.get("quantity"))

    for row in read_list("inventory_registry"):
        if not row.get("active", True):
            continue
        item_id = str(row.get("item_id") or row.get("catalog_item_id") or "")
        physical = _num(row.get("available_quantity", row.get("quantity", row.get("stock", 0.0))))
        available = max(physical - reserved_by_item.get(item_id, 0.0), 0.0)
        minimum = _num(row.get("minimum_stock", row.get("reorder_point", 0.0)))
        if available <= 0:
            out += 1
        elif minimum > 0 and available <= minimum:
            low += 1
    return low, out


def _pending_receivables() -> float:
    rows = read_list("receivables_registry")
    return sum(
        max(_num(row.get("balance", row.get("pending_amount", row.get("amount_due", 0.0)))), 0.0)
        for row in rows
        if str(row.get("status", "Pendiente")).casefold() not in {"pagado", "pagada", "cerrado", "cerrada"}
    )


def _pending_payables() -> float:
    rows = read_list("payables_registry")
    return sum(
        max(_num(row.get("balance", row.get("pending_amount", row.get("amount_due", 0.0)))), 0.0)
        for row in rows
        if str(row.get("status", "Pendiente")).casefold() not in {"pagado", "pagada", "cerrado", "cerrada"}
    )


def _deliveries_due(rows: list[dict]) -> int:
    today = date.today()
    return sum(
        1 for row in rows
        if str(row.get("order_status", "Pendiente")).casefold() not in {"entregado", "entregada"}
        and _date_value(row.get("delivery_date") or row.get("due_date") or row.get("expected_date")) == today
    )


def _production_active() -> int:
    return sum(
        1 for row in read_list("production_log")
        if str(row.get("status", "Pendiente")).casefold()
        not in {"completada", "completado", "cerrada", "cerrado", "cancelada", "cancelado"}
    )


def _recent_activity() -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    sources = (
        ("sales_registry", "Venta", "order_id", "customer_name"),
        ("catalog_purchase_orders", "Compra", "purchase_id", "supplier"),
        ("goods_receipts", "Recepción", "receipt_id", "item_name"),
        ("inventory_movements", "Inventario", "movement_type", "item_name"),
        ("customers_registry", "Cliente", "customer_id", "name"),
    )
    for key, event_type, reference_key, label_key in sources:
        for row in read_list(key)[-20:]:
            timestamp = str(
                row.get("created_at_utc")
                or row.get("accepted_at_utc")
                or row.get("updated_at_utc")
                or ""
            )
            events.append({
                "timestamp": timestamp,
                "type": event_type,
                "reference": str(row.get(reference_key) or ""),
                "label": str(row.get(label_key) or "Sin detalle"),
            })
    return sorted(events, key=lambda row: row["timestamp"], reverse=True)[:8]


def _navigate(area: str, page: str) -> None:
    st.session_state["navigation_area"] = area
    st.session_state["navigation_page"] = page
    st.rerun()


def _render_styles() -> None:
    st.markdown(
        """
        <style>
        .cm-home-hero{padding:1.35rem 1.45rem;border:1px solid rgba(109,74,255,.16);border-radius:22px;background:linear-gradient(135deg,rgba(109,74,255,.12),rgba(34,166,161,.09));margin-bottom:1rem}
        .cm-home-hero__eyebrow{font-size:.75rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#6d4aff}
        .cm-home-hero__title{font-size:1.7rem;font-weight:850;color:#172033;margin:.25rem 0}
        .cm-home-hero__copy{color:#64748b;max-width:760px}
        .cm-alert-card{padding:.9rem 1rem;border:1px solid rgba(148,163,184,.22);border-radius:16px;background:white;margin:.35rem 0}
        .cm-alert-card strong{display:block;color:#172033}.cm-alert-card span{font-size:.86rem;color:#64748b}
        .cm-activity{padding:.72rem .85rem;border-left:3px solid rgba(109,74,255,.35);background:rgba(248,250,252,.8);border-radius:0 12px 12px 0;margin:.45rem 0}
        .cm-activity strong{color:#172033}.cm-activity small{display:block;color:#64748b;margin-top:.15rem}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_home_dashboard_safe() -> None:
    """Muestra un centro de decisiones sin modificar datos operativos."""
    _render_styles()
    user = auth.current_user()
    display_name = user.display_name if user else "Copy Mary"
    sales = _active_sales()
    pending_purchases = _pending_purchase_rows()
    low_stock, out_of_stock = _inventory_alerts()
    receivables = _pending_receivables()
    payables = _pending_payables()
    deliveries_today = _deliveries_due(sales)
    production_active = _production_active()

    st.markdown(
        f'<div class="cm-home-hero"><div class="cm-home-hero__eyebrow">Centro ejecutivo</div>'
        f'<div class="cm-home-hero__title">Buenos días, {display_name}</div>'
        '<div class="cm-home-hero__copy">Revisa el estado del negocio, atiende alertas y abre las tareas prioritarias desde un solo lugar.</div></div>',
        unsafe_allow_html=True,
    )

    metrics = st.columns(6)
    metrics[0].metric("Ventas de hoy", f"${_sales_total_today(sales):,.2f}")
    metrics[1].metric("Compras por recibir", len(pending_purchases))
    metrics[2].metric("Producción activa", production_active)
    metrics[3].metric("Entregas de hoy", deliveries_today)
    metrics[4].metric("Cobros pendientes", f"${receivables:,.2f}")
    metrics[5].metric("Pagos pendientes", f"${payables:,.2f}")

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("### Alertas y trabajo pendiente")
        alerts = [
            (out_of_stock > 0, "Inventario agotado", f"{out_of_stock} artículo(s) sin disponibilidad.", "Inventario y almacén", "Inventario"),
            (low_stock > 0, "Stock bajo", f"{low_stock} artículo(s) alcanzaron su mínimo.", "Inventario y almacén", "Inventario"),
            (len(pending_purchases) > 0, "Compras esperando recepción", f"{len(pending_purchases)} orden(es) todavía no ingresan al inventario.", "Compras y abastecimiento", "Recepción de mercancía"),
            (deliveries_today > 0, "Entregas para hoy", f"{deliveries_today} pedido(s) requieren seguimiento.", "Comercial y CRM", "Agenda de producción y entregas"),
            (receivables > 0, "Cobros pendientes", f"Saldo pendiente: ${receivables:,.2f}.", "Comercial y CRM", "Cuentas por cobrar"),
            (payables > 0, "Pagos a proveedores", f"Saldo pendiente: ${payables:,.2f}.", "Compras y abastecimiento", "Cuentas por pagar"),
        ]
        visible_alerts = [item for item in alerts if item[0]]
        if not visible_alerts:
            st.success("No hay alertas operativas con los datos actuales.")
        for index, (_, title, detail, area, page) in enumerate(visible_alerts):
            with st.container(border=True):
                a, b = st.columns([4, 1])
                a.markdown(f"**{title}**")
                a.caption(detail)
                if b.button("Abrir", key=f"home_alert_{index}", use_container_width=True):
                    _navigate(area, page)

    with right:
        st.markdown("### Actividad reciente")
        recent = _recent_activity()
        if not recent:
            st.info("Todavía no hay actividad reciente para mostrar.")
        for event in recent:
            timestamp = event["timestamp"][:16].replace("T", " ") if event["timestamp"] else "Sin fecha"
            st.markdown(
                f'<div class="cm-activity"><strong>{event["type"]}: {event["label"]}</strong>'
                f'<small>{event["reference"] or "Sin referencia"} · {timestamp} UTC</small></div>',
                unsafe_allow_html=True,
            )

    st.markdown("### Acciones rápidas")
    action_columns = st.columns(4)
    for index, (label, (area, page)) in enumerate(_NAVIGATION_TARGETS.items()):
        with action_columns[index % 4]:
            if st.button(label, key=f"home_quick_action_{index}", use_container_width=True, type="primary" if index < 2 else "secondary"):
                _navigate(area, page)

    st.markdown("### Estado general")
    status = st.columns(4)
    status[0].metric("Clientes", len(read_list("customers_registry")))
    status[1].metric("Pedidos activos", sum(str(row.get("order_status", "Pendiente")).casefold() not in {"entregado", "entregada"} for row in sales))
    status[2].metric("Artículos en catálogo", len(read_list("catalog_items")))
    status[3].metric("Recepciones registradas", len(read_list("goods_receipts")))

    st.caption(
        "Panel de solo lectura. Los datos se originan en los módulos operativos y esta pantalla no modifica ventas, compras, inventario, producción ni finanzas."
    )
