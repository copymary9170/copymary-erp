"""Historial, checklist y control de entrega para ventas y pedidos."""

from datetime import date, datetime
from uuid import uuid4
import csv
import io

import streamlit as st

from src import sales_orders_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    section = "order_events"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Historial de pedidos"
        session_backup.SESSION_KEYS = (
            "general_settings",
            *session_backup.LIST_SECTIONS,
            *session_backup.DICT_SECTIONS,
        )


_activate_backup()


def _as_datetime(value) -> datetime | None:
    raw = str(value or "")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _update_sale(sale_id: str, updates: dict) -> None:
    sales = _rows("sales_registry")
    for sale in sales:
        if str(sale.get("sale_id", "")) == sale_id:
            sale.update(updates)
            sale["updated_at_utc"] = _now()
    _save("sales_registry", sales)


def _add_event(order_id: str, event_type: str, note: str, responsible: str) -> None:
    events = _rows("order_events")
    events.append({
        "event_id": uuid4().hex[:12],
        "sale_id": order_id,
        "event_type": event_type,
        "note": note.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("order_events", events)


def _export(sales: list[dict], clients: list[dict], events: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Cliente", "Descripción", "Estado", "Pago", "Prioridad", "Entrega", "Responsable", "Checklist", "Eventos"])
    for sale in sales:
        sale_id = str(sale.get("sale_id", ""))
        checklist = sale.get("order_checklist", {}) if isinstance(sale.get("order_checklist"), dict) else {}
        completed = sum(1 for value in checklist.values() if value)
        writer.writerow([
            sale_id,
            _client_name(str(sale.get("client_id", "")), clients),
            sale.get("description", ""),
            sale.get("order_status", ""),
            sale.get("payment_status", ""),
            sale.get("priority", "Normal"),
            sale.get("due_date", ""),
            sale.get("responsible", ""),
            f"{completed}/{len(checklist)}" if checklist else "0/0",
            sum(1 for event in events if str(event.get("sale_id", "")) == sale_id),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_sales_orders_tracking() -> None:
    render_page_header(
        "Ventas y pedidos",
        "Producción, historial, checklist y confirmación de entrega para controlar cada pedido.",
    )
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_sales_orders_plus()
    finally:
        base.render_page_header = original_header

    clients = _rows("customers_registry")
    sales = _rows("sales_registry")
    events = _rows("order_events")
    active = [sale for sale in sales if sale.get("order_status") not in {"Entregado", "Cancelado"}]
    stalled = []
    for sale in active:
        last_change = _as_datetime(sale.get("updated_at_utc") or sale.get("created_at_utc"))
        if last_change and (date.today() - last_change.date()).days >= 3:
            stalled.append(sale)

    st.divider()
    metrics = st.columns(4)
    metrics[0].metric("Pedidos con historial", str(len({str(item.get('sale_id', '')) for item in events})))
    metrics[1].metric("Pedidos detenidos", str(len(stalled)))
    metrics[2].metric("Entregados", str(sum(1 for sale in sales if sale.get("order_status") == "Entregado")))
    metrics[3].metric("Cancelados", str(sum(1 for sale in sales if sale.get("order_status") == "Cancelado")))

    if stalled:
        st.warning(f"Hay {len(stalled)} pedido(s) activos sin actualización durante 3 días o más.")

    if sales:
        st.download_button(
            "Descargar seguimiento de pedidos CSV",
            data=_export(sales, clients, events),
            file_name=f"seguimiento_pedidos_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    options = {
        f"{sale.get('description', 'Pedido')} · {sale.get('sale_id', '')} · {_client_name(str(sale.get('client_id', '')), clients)}": str(sale.get("sale_id", ""))
        for sale in sales
    }
    if not options:
        st.info("Registra una venta o pedido para usar el seguimiento avanzado.")
        return

    selected = st.selectbox("Pedido para gestionar", tuple(options.keys()), key="order_tracking_selected")
    sale_id = options[selected]
    sale = next((item for item in sales if str(item.get("sale_id", "")) == sale_id), {})
    checklist = sale.get("order_checklist", {}) if isinstance(sale.get("order_checklist"), dict) else {}

    checklist_tab, event_tab, delivery_tab, history_tab = st.tabs(("Checklist", "Registrar novedad", "Entrega o cancelación", "Historial"))

    with checklist_tab:
        with st.form("order_checklist_form"):
            material_ready = st.checkbox("Material preparado", value=bool(checklist.get("material_ready")))
            design_approved = st.checkbox("Diseño o contenido aprobado", value=bool(checklist.get("design_approved")))
            production_done = st.checkbox("Producción terminada", value=bool(checklist.get("production_done")))
            quality_checked = st.checkbox("Calidad verificada", value=bool(checklist.get("quality_checked")))
            packaged = st.checkbox("Empacado", value=bool(checklist.get("packaged")))
            customer_notified = st.checkbox("Cliente notificado", value=bool(checklist.get("customer_notified")))
            responsible = st.text_input("Responsable de la revisión", value=str(sale.get("responsible", "")))
            save_checklist = st.form_submit_button("Guardar checklist", type="primary", use_container_width=True)
        if save_checklist:
            values = {
                "material_ready": material_ready,
                "design_approved": design_approved,
                "production_done": production_done,
                "quality_checked": quality_checked,
                "packaged": packaged,
                "customer_notified": customer_notified,
            }
            _update_sale(sale_id, {"order_checklist": values})
            _add_event(sale_id, "Checklist actualizado", f"Completados {sum(values.values())} de {len(values)} pasos.", responsible)
            st.rerun()

    with event_tab:
        with st.form("order_event_form", clear_on_submit=True):
            event_type = st.selectbox("Tipo de novedad", ("Cambio solicitado", "Producción", "Incidencia", "Contacto con cliente", "Control de calidad", "Otro"))
            note = st.text_area("Detalle", max_chars=700)
            responsible = st.text_input("Responsable", placeholder="Mary")
            save_event = st.form_submit_button("Registrar novedad", type="primary", use_container_width=True)
        if save_event:
            if not note.strip():
                st.error("Escribe el detalle de la novedad.")
            else:
                _add_event(sale_id, event_type, note, responsible)
                _update_sale(sale_id, {})
                st.rerun()

    with delivery_tab:
        with st.form("order_close_form"):
            action = st.selectbox("Acción", ("Confirmar entrega", "Cancelar pedido"))
            responsible = st.text_input("Responsable", value=str(sale.get("responsible", "")), key="order_close_owner")
            received_by = st.text_input("Recibido por", value=str(sale.get("received_by", "")))
            reason = st.text_area("Observación o motivo", max_chars=500)
            confirm = st.form_submit_button("Guardar acción", use_container_width=True)
        if confirm:
            if action == "Cancelar pedido" and not reason.strip():
                st.error("Indica el motivo de cancelación.")
            else:
                status = "Entregado" if action == "Confirmar entrega" else "Cancelado"
                updates = {
                    "order_status": status,
                    "received_by": received_by.strip(),
                    "delivery_confirmed_at_utc": _now() if status == "Entregado" else "",
                    "cancellation_reason": reason.strip() if status == "Cancelado" else "",
                    "cancelled_at_utc": _now() if status == "Cancelado" else "",
                }
                _update_sale(sale_id, updates)
                _add_event(sale_id, action, reason or f"Recibido por {received_by or 'no indicado'}", responsible)
                st.rerun()

    with history_tab:
        order_events = [item for item in events if str(item.get("sale_id", "")) == sale_id]
        if not order_events:
            st.info("Este pedido todavía no tiene historial registrado.")
        for event in reversed(order_events):
            with st.container(border=True):
                st.markdown(f"**{event.get('event_type', 'Novedad')}**")
                st.write(str(event.get("note", "")))
                st.caption(f"{event.get('created_at_utc', '')} · {event.get('responsible', 'Sin asignar')}")

    render_info_card(
        "Trazabilidad del pedido",
        "Checklist, novedades, entregas y cancelaciones se incluyen en el respaldo general.",
        "CONTROL OPERATIVO",
    )
