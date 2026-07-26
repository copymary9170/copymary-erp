"""Panel ejecutivo seguro para la pantalla de Inicio.

Esta implementación consulta datos ya presentes en ``st.session_state`` y el
estado técnico de la base de datos. No crea, modifica ni elimina registros.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

from src import auth
from src.config import APP_VERSION, PROJECT_STATUS
from src.erp_database import get_database_status
from src.home_dashboard_phase3 import render_phase3_sections
from src.home_dashboard_phase4 import render_preferences_panel
from src.home_dashboard_phase5 import render_phase5_sections
from src.home_dashboard_phase6 import render_phase6_sections
from src.session_backup import latest_snapshot_info
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


def _pending_balance(key: str) -> float:
    return sum(
        max(_num(row.get("balance", row.get("pending_amount", row.get("amount_due", 0.0)))), 0.0)
        for row in read_list(key)
        if str(row.get("status", "Pendiente")).casefold()
        not in {"pagado", "pagada", "cerrado", "cerrada"}
    )


def _deliveries_due(rows: list[dict], target: date) -> list[dict]:
    return [
        row for row in rows
        if str(row.get("order_status", "Pendiente")).casefold() not in {"entregado", "entregada"}
        and _date_value(row.get("delivery_date") or row.get("due_date") or row.get("expected_date")) == target
    ]


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


def _system_status() -> tuple[dict[str, str], str | None]:
    try:
        database = get_database_status()
        snapshot = latest_snapshot_info()
    except (RuntimeError, OSError, ValueError) as exc:
        return {}, f"No se pudo consultar el estado técnico: {exc}"

    last_backup = "Sin respaldo"
    if snapshot and snapshot.get("created_at_utc"):
        last_backup = str(snapshot["created_at_utc"])[:16].replace("T", " ") + " UTC"
    return {
        "Base de datos": "PostgreSQL" if database.engine == "postgresql" else "SQLite local",
        "Estado": "Operativa" if database.ready else "Requiere revisión",
        "Último respaldo": last_backup,
        "Versión": f"{APP_VERSION} · {PROJECT_STATUS}",
    }, None


def _render_styles() -> None:
    st.markdown(
        """
        <style>
        .cm-home-hero{padding:1.35rem 1.45rem;border:1px solid rgba(109,74,255,.16);border-radius:22px;background:linear-gradient(135deg,rgba(109,74,255,.12),rgba(34,166,161,.09));margin-bottom:1rem}
        .cm-home-hero__eyebrow{font-size:.75rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#6d4aff}
        .cm-home-hero__title{font-size:1.7rem;font-weight:850;color:#172033;margin:.25rem 0}
        .cm-home-hero__copy{color:#64748b;max-width:760px}
        .cm-activity{padding:.72rem .85rem;border-left:3px solid rgba(109,74,255,.35);background:rgba(248,250,252,.8);border-radius:0 12px 12px 0;margin:.45rem 0}
        .cm-activity strong{color:#172033}.cm-activity small{display:block;color:#64748b;margin-top:.15rem}
        .cm-flow{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.45rem;margin:.7rem 0 1.2rem}
        .cm-flow__step{padding:.85rem .55rem;border:1px solid rgba(148,163,184,.22);border-radius:14px;background:white;text-align:center}
        .cm-flow__step strong{display:block;color:#172033;font-size:.88rem}.cm-flow__step span{display:block;color:#6d4aff;font-weight:800;font-size:1.05rem;margin-top:.2rem}
        @media(max-width:900px){.cm-flow{grid-template-columns:repeat(2,minmax(0,1fr))}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_business_flow(pending_purchases: int, receipts: int, inventory_items: int, production: int, sales: list[dict], receivables: float) -> None:
    steps = (
        ("Compras", pending_purchases),
        ("Recepción", receipts),
        ("Inventario", inventory_items),
        ("Producción", production),
        ("Ventas", len(sales)),
        ("Cobros", int(receivables > 0)),
        ("Caja", len(read_list("cash_movements"))),
    )
    cards = "".join(
        f'<div class="cm-flow__step"><strong>{label}</strong><span>{value}</span></div>'
        for label, value in steps
    )
    st.markdown(f'<div class="cm-flow">{cards}</div>', unsafe_allow_html=True)


def render_home_dashboard_safe() -> None:
    """Muestra un centro de decisiones sin modificar datos operativos."""
    _render_styles()
    user = auth.current_user()
    display_name = user.display_name if user else "Copy Mary"
    role_name = user.role_name if user else "Sin rol"
    user_id = user.user_id if user else "anonymous"
    preferences = render_preferences_panel(user_id, role_name)
    visible_widgets = set(preferences.visible_widgets)

    sales = _active_sales()
    pending_purchases = _pending_purchase_rows()
    low_stock, out_of_stock = _inventory_alerts()
    receivables = _pending_balance("receivables_registry")
    payables = _pending_balance("payables_registry")
    deliveries_today = _deliveries_due(sales, date.today())
    production_active = _production_active()
    receipts = read_list("goods_receipts")
    inventory = read_list("inventory_registry")
    sales_today = _sales_total_today(sales)

    st.markdown(
        f'<div class="cm-home-hero"><div class="cm-home-hero__eyebrow">Torre de control empresarial</div>'
        f'<div class="cm-home-hero__title">Buenos días, {display_name}</div>'
        f'<div class="cm-home-hero__copy">Perfil activo: {preferences.profile}. Decide qué atender primero y muestra solo los widgets necesarios para tu trabajo.</div></div>',
        unsafe_allow_html=True,
    )

    if "executive_metrics" in visible_widgets:
        metrics = st.columns(6)
        metrics[0].metric("Ventas de hoy", f"${sales_today:,.2f}")
        metrics[1].metric("Compras por recibir", len(pending_purchases))
        metrics[2].metric("Producción activa", production_active)
        metrics[3].metric("Entregas de hoy", len(deliveries_today))
        metrics[4].metric("Cobros pendientes", f"${receivables:,.2f}")
        metrics[5].metric("Pagos pendientes", f"${payables:,.2f}")

    if "business_flow" in visible_widgets:
        st.markdown("### Flujo del negocio")
        _render_business_flow(len(pending_purchases), len(receipts), len(inventory), production_active, sales, receivables)

    if "priorities" in visible_widgets or "agenda" in visible_widgets:
        left, right = st.columns([1.08, 1])
        with left:
            if "priorities" in visible_widgets:
                st.markdown("### Prioridades")
                alerts = [
                    (out_of_stock > 0, "Crítica", "Inventario agotado", f"{out_of_stock} artículo(s) sin disponibilidad.", "Inventario y almacén", "Inventario"),
                    (low_stock > 0, "Alta", "Stock bajo", f"{low_stock} artículo(s) alcanzaron su mínimo.", "Inventario y almacén", "Inventario"),
                    (len(pending_purchases) > 0, "Alta", "Compras esperando recepción", f"{len(pending_purchases)} orden(es) todavía no ingresan al inventario.", "Compras y abastecimiento", "Recepción de mercancía"),
                    (len(deliveries_today) > 0, "Alta", "Entregas para hoy", f"{len(deliveries_today)} pedido(s) requieren seguimiento.", "Comercial y CRM", "Agenda de producción y entregas"),
                    (receivables > 0, "Media", "Cobros pendientes", f"Saldo pendiente: ${receivables:,.2f}.", "Comercial y CRM", "Cuentas por cobrar"),
                    (payables > 0, "Media", "Pagos a proveedores", f"Saldo pendiente: ${payables:,.2f}.", "Compras y abastecimiento", "Cuentas por pagar"),
                ]
                visible_alerts = [item for item in alerts if item[0]]
                if not visible_alerts:
                    st.success("No hay alertas operativas con los datos actuales.")
                for index, (_, priority, title, detail, area, page) in enumerate(visible_alerts):
                    with st.container(border=True):
                        a, b = st.columns([4, 1])
                        a.markdown(f"**{priority} · {title}**")
                        a.caption(detail)
                        if b.button("Abrir", key=f"home_alert_{index}", use_container_width=True):
                            _navigate(area, page)

        with right:
            if "agenda" in visible_widgets:
                st.markdown("### Agenda de hoy")
                if deliveries_today:
                    for row in deliveries_today[:6]:
                        customer = str(row.get("customer_name") or "Cliente sin nombre")
                        reference = str(row.get("order_id") or row.get("sale_id") or "Sin referencia")
                        st.markdown(f"- **Entrega:** {customer} · {reference}")
                else:
                    st.info("No hay entregas programadas para hoy.")
                if pending_purchases:
                    st.caption(f"También hay {len(pending_purchases)} compra(s) pendientes de recepción.")

                st.markdown("### Actividad reciente")
                recent = _recent_activity()
                if not recent:
                    st.info("Todavía no hay actividad reciente para mostrar.")
                for event in recent[:5]:
                    timestamp = event["timestamp"][:16].replace("T", " ") if event["timestamp"] else "Sin fecha"
                    st.markdown(
                        f'<div class="cm-activity"><strong>{event["type"]}: {event["label"]}</strong>'
                        f'<small>{event["reference"] or "Sin referencia"} · {timestamp} UTC</small></div>',
                        unsafe_allow_html=True,
                    )

    if "phase3" in visible_widgets:
        render_phase3_sections(
            sales_today=sales_today,
            pending_purchases=len(pending_purchases),
            low_stock=low_stock,
            out_of_stock=out_of_stock,
            deliveries_today=len(deliveries_today),
            receivables=receivables,
            payables=payables,
        )
        st.caption(f"Periodo seleccionado para tendencias: {preferences.chart_days} días. La fase 3 actual conserva su serie de 7 días.")

    if "phase5" in visible_widgets:
        render_phase5_sections(preferences.chart_days)

    if "phase6" in visible_widgets:
        render_phase6_sections(user_id)

    if "quick_actions" in visible_widgets:
        st.markdown("### Acciones rápidas")
        action_columns = st.columns(4)
        for index, (label, (area, page)) in enumerate(_NAVIGATION_TARGETS.items()):
            with action_columns[index % 4]:
                if st.button(label, key=f"home_quick_action_{index}", use_container_width=True, type="primary" if index < 2 else "secondary"):
                    _navigate(area, page)

    if "system_status" in visible_widgets:
        st.markdown("### Estado general y técnico")
        business_status = st.columns(4)
        business_status[0].metric("Clientes", len(read_list("customers_registry")))
        business_status[1].metric("Pedidos activos", sum(str(row.get("order_status", "Pendiente")).casefold() not in {"entregado", "entregada"} for row in sales))
        business_status[2].metric("Artículos en catálogo", len(read_list("catalog_items")))
        business_status[3].metric("Recepciones registradas", len(receipts))

        technical, technical_error = _system_status()
        if technical_error:
            st.warning(technical_error)
        elif technical:
            technical_columns = st.columns(4)
            for column, (label, value) in zip(technical_columns, technical.items(), strict=True):
                column.metric(label, value)

    st.caption(
        "Panel de solo lectura. La personalización, la analítica y las metas de sesión no modifican ventas, compras, inventario, producción ni finanzas."
    )
