"""Gestión ampliada de compras para CopyMary ERP."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import purchasing as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money


def _activate_backup() -> None:
    for section, label in (
        ("purchase_requests", "Solicitudes de compra"),
        ("purchase_events", "Historial de compras"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = (
        "general_settings",
        *session_backup.LIST_SECTIONS,
        *session_backup.DICT_SECTIONS,
    )


_activate_backup()


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, rows: list[dict]) -> None:
    st.session_state[key] = rows


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _supplier_name(supplier_id: str, suppliers: list[dict]) -> str:
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")) == supplier_id:
            return str(supplier.get("name", "Proveedor"))
    return "Sin proveedor"


def _update_purchase(purchase_id: str, updates: dict) -> None:
    purchases = _rows("purchases_registry")
    for purchase in purchases:
        if str(purchase.get("purchase_id", "")) == purchase_id:
            purchase.update(updates)
            purchase["updated_at_utc"] = _now()
    _save("purchases_registry", purchases)


def _add_event(purchase_id: str, event_type: str, note: str, responsible: str = "") -> None:
    events = _rows("purchase_events")
    events.append({
        "event_id": uuid4().hex[:12],
        "purchase_id": purchase_id,
        "event_type": event_type,
        "note": note.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("purchase_events", events)


def _export(purchases: list[dict], suppliers: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Compra", "Fecha", "Proveedor", "Material", "Cantidad", "Unidad", "Costo unitario",
        "Total", "Pago", "Recepción", "Entrega esperada", "Recibido", "Pendiente", "Prioridad",
    ])
    for purchase in purchases:
        quantity = _num(purchase.get("quantity"))
        received = _num(purchase.get("received_quantity"), quantity if purchase.get("receipt_status") == "Recibida" else 0.0)
        writer.writerow([
            purchase.get("purchase_id", ""),
            purchase.get("created_at_utc", ""),
            _supplier_name(str(purchase.get("supplier_id", "")), suppliers),
            purchase.get("material_name", ""),
            quantity,
            purchase.get("unit_name", "unidad"),
            _num(purchase.get("unit_cost")),
            _num(purchase.get("total")),
            purchase.get("payment_status", ""),
            purchase.get("receipt_status", ""),
            purchase.get("expected_date", ""),
            received,
            max(quantity - received, 0.0),
            purchase.get("priority", "Normal"),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_purchases_plus() -> None:
    render_page_header(
        "Compras",
        "Planifica, recibe y controla compras con fechas, prioridades, recepciones parciales e historial.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_purchases()
    finally:
        base.render_page_header = original_header

    purchases = _rows("purchases_registry")
    suppliers = _rows("suppliers_registry")
    requests = _rows("purchase_requests")
    events = _rows("purchase_events")
    today = date.today()

    open_purchases = [item for item in purchases if str(item.get("receipt_status", "Pendiente")) not in {"Recibida", "Cancelada"}]
    overdue = [
        item for item in open_purchases
        if _as_date(item.get("expected_date")) and _as_date(item.get("expected_date")) < today
    ]
    due_soon = [
        item for item in open_purchases
        if _as_date(item.get("expected_date")) and today <= _as_date(item.get("expected_date")) <= today + timedelta(days=7)
    ]
    unpaid_total = sum(_num(item.get("total")) for item in purchases if str(item.get("payment_status", "")) != "Pagado")

    st.divider()
    st.markdown("### Control de compras")
    metrics = st.columns(4)
    metrics[0].metric("Compras abiertas", str(len(open_purchases)))
    metrics[1].metric("Atrasadas", str(len(overdue)))
    metrics[2].metric("Llegan en 7 días", str(len(due_soon)))
    metrics[3].metric("Pendiente de pago", format_money(unpaid_total))

    if overdue:
        st.error(f"Hay {len(overdue)} compra(s) con fecha esperada vencida.")

    request_tab, planning_tab, receipt_tab, history_tab, report_tab = st.tabs(
        ("Solicitud", "Planificación", "Recepción parcial", "Historial", "Reporte")
    )

    with request_tab:
        with st.form("purchase_request_form", clear_on_submit=True):
            columns = st.columns(4)
            material = columns[0].text_input("Material o producto")
            quantity = columns[1].number_input("Cantidad requerida", min_value=0.01, value=1.0, step=1.0)
            unit = columns[2].text_input("Unidad", value="unidad")
            priority = columns[3].selectbox("Prioridad", ("Baja", "Normal", "Alta", "Urgente"))
            second = st.columns(3)
            needed_date = second[0].date_input("Fecha necesaria", value=today + timedelta(days=7))
            requested_by = second[1].text_input("Solicitado por")
            budget = second[2].number_input("Presupuesto máximo", min_value=0.0, value=0.0, step=1.0)
            reason = st.text_area("Motivo de la compra", max_chars=500)
            submitted = st.form_submit_button("Crear solicitud", type="primary", use_container_width=True)
        if submitted:
            if not material.strip():
                st.error("Indica el material o producto requerido.")
            else:
                requests.append({
                    "request_id": f"REQ-{uuid4().hex[:8].upper()}",
                    "material_name": material.strip(),
                    "quantity": float(quantity),
                    "unit_name": unit.strip() or "unidad",
                    "priority": priority,
                    "needed_date": needed_date.isoformat(),
                    "requested_by": requested_by.strip() or "Sin asignar",
                    "budget": float(budget),
                    "reason": reason.strip(),
                    "status": "Pendiente",
                    "created_at_utc": _now(),
                })
                _save("purchase_requests", requests)
                st.rerun()

        for request in reversed(requests[-30:]):
            with st.container(border=True):
                columns = st.columns([3, 1, 1, 1])
                columns[0].markdown(f"**{request.get('material_name', 'Solicitud')}**")
                columns[0].caption(f"{request.get('request_id', '')} · {request.get('requested_by', '')}")
                columns[1].metric("Cantidad", f"{_num(request.get('quantity')):,.2f} {request.get('unit_name', '')}")
                columns[2].metric("Prioridad", str(request.get("priority", "Normal")))
                columns[3].metric("Estado", str(request.get("status", "Pendiente")))
                if request.get("status") == "Pendiente" and st.button("Marcar aprobada", key=f"approve_request_{request.get('request_id')}", use_container_width=True):
                    updated = []
                    for current in requests:
                        row = dict(current)
                        if row.get("request_id") == request.get("request_id"):
                            row["status"] = "Aprobada"
                            row["approved_at_utc"] = _now()
                        updated.append(row)
                    _save("purchase_requests", updated)
                    st.rerun()

    purchase_options = {
        f"{item.get('material_name', 'Compra')} · {item.get('purchase_id', '')}": str(item.get("purchase_id", ""))
        for item in purchases
    }

    with planning_tab:
        if not purchase_options:
            st.info("No hay compras registradas.")
        else:
            selected = st.selectbox("Compra", tuple(purchase_options.keys()), key="purchase_plan_selected")
            purchase_id = purchase_options[selected]
            purchase = next(item for item in purchases if str(item.get("purchase_id", "")) == purchase_id)
            with st.form("purchase_planning_form"):
                columns = st.columns(4)
                expected_date = columns[0].date_input("Entrega esperada", value=_as_date(purchase.get("expected_date")) or today + timedelta(days=7))
                priority = columns[1].selectbox("Prioridad", ("Baja", "Normal", "Alta", "Urgente"), index=("Baja", "Normal", "Alta", "Urgente").index(str(purchase.get("priority", "Normal"))) if str(purchase.get("priority", "Normal")) in ("Baja", "Normal", "Alta", "Urgente") else 1)
                responsible = columns[2].text_input("Responsable", value=str(purchase.get("responsible", "")))
                order_reference = columns[3].text_input("Orden o referencia", value=str(purchase.get("order_reference", "")))
                notes = st.text_area("Seguimiento", value=str(purchase.get("followup_notes", "")))
                save_plan = st.form_submit_button("Guardar planificación", type="primary", use_container_width=True)
            if save_plan:
                _update_purchase(purchase_id, {
                    "expected_date": expected_date.isoformat(),
                    "priority": priority,
                    "responsible": responsible.strip(),
                    "order_reference": order_reference.strip(),
                    "followup_notes": notes.strip(),
                })
                _add_event(purchase_id, "Planificación actualizada", f"Entrega esperada: {expected_date.isoformat()}", responsible)
                st.rerun()

    with receipt_tab:
        open_options = {
            label: purchase_id for label, purchase_id in purchase_options.items()
            if next(item for item in purchases if str(item.get("purchase_id", "")) == purchase_id).get("receipt_status") != "Cancelada"
        }
        if not open_options:
            st.info("No hay compras disponibles para recibir.")
        else:
            selected = st.selectbox("Compra", tuple(open_options.keys()), key="purchase_receipt_selected")
            purchase_id = open_options[selected]
            purchase = next(item for item in purchases if str(item.get("purchase_id", "")) == purchase_id)
            ordered = _num(purchase.get("quantity"))
            already_received = _num(purchase.get("received_quantity"), ordered if purchase.get("receipt_status") == "Recibida" else 0.0)
            remaining = max(ordered - already_received, 0.0)
            st.caption(f"Pedido: {ordered:,.2f} · Recibido: {already_received:,.2f} · Pendiente: {remaining:,.2f}")
            with st.form("partial_receipt_form"):
                received_now = st.number_input("Cantidad recibida ahora", min_value=0.0, max_value=float(remaining), value=float(remaining), step=1.0)
                condition = st.selectbox("Condición", ("Conforme", "Con faltantes", "Dañado", "Diferencia de precio", "Otro"))
                responsible = st.text_input("Recibido por")
                note = st.text_area("Observación de recepción", max_chars=500)
                submit_receipt = st.form_submit_button("Registrar recepción", type="primary", use_container_width=True)
            if submit_receipt:
                if received_now <= 0:
                    st.error("La cantidad recibida debe ser mayor que cero.")
                else:
                    total_received = min(already_received + float(received_now), ordered)
                    status = "Recibida" if total_received >= ordered else "Parcial"
                    _update_purchase(purchase_id, {
                        "received_quantity": total_received,
                        "receipt_status": status,
                        "last_receipt_condition": condition,
                        "last_received_at_utc": _now(),
                    })
                    _add_event(purchase_id, "Recepción registrada", f"{received_now:,.2f} recibida(s). Condición: {condition}. {note}", responsible)
                    st.rerun()

    with history_tab:
        selected_filter = st.selectbox("Filtrar compra", ("Todas", *purchase_options.keys()), key="purchase_history_filter")
        filtered_events = events
        if selected_filter != "Todas":
            filtered_events = [item for item in events if str(item.get("purchase_id", "")) == purchase_options[selected_filter]]
        if not filtered_events:
            st.info("No hay movimientos registrados.")
        for event in reversed(filtered_events[-100:]):
            with st.container(border=True):
                st.markdown(f"**{event.get('event_type', 'Movimiento')} · {event.get('purchase_id', '')}**")
                st.write(str(event.get("note", "")))
                st.caption(f"{event.get('created_at_utc', '')} · {event.get('responsible', 'Sin asignar')}")

    with report_tab:
        category_totals: dict[str, float] = defaultdict(float)
        supplier_totals: dict[str, float] = defaultdict(float)
        for purchase in purchases:
            category_totals[str(purchase.get("category", "Otro"))] += _num(purchase.get("total"))
            supplier_totals[_supplier_name(str(purchase.get("supplier_id", "")), suppliers)] += _num(purchase.get("total"))
        st.markdown("#### Compras por categoría")
        for category, amount in sorted(category_totals.items(), key=lambda item: item[1], reverse=True):
            st.write(f"**{category}:** {format_money(amount)}")
        st.markdown("#### Compras por proveedor")
        for supplier, amount in sorted(supplier_totals.items(), key=lambda item: item[1], reverse=True)[:10]:
            st.write(f"**{supplier}:** {format_money(amount)}")
        if purchases:
            st.download_button(
                "Descargar compras CSV",
                data=_export(purchases, suppliers),
                file_name=f"compras_{today.isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    render_info_card(
        "Compra controlada",
        "Solicitudes, fechas, recepciones parciales e historial quedan incluidos en el respaldo general.",
        "COMPRAS",
    )
