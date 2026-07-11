"""Entrega, reimpresión y seguimiento de comprobantes."""

from datetime import date
from uuid import uuid4

import streamlit as st

from src import receipts_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    section = "receipt_events"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Historial de comprobantes"
        session_backup.SESSION_KEYS = (
            "general_settings",
            *session_backup.LIST_SECTIONS,
            *session_backup.DICT_SECTIONS,
        )


_activate_backup()


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _update_receipt(receipt_id: str, updates: dict) -> None:
    receipts = _rows("receipts_registry")
    for receipt in receipts:
        if str(receipt.get("receipt_id", "")) == receipt_id:
            receipt.update(updates)
            receipt["updated_at_utc"] = _now()
    _save("receipts_registry", receipts)


def _add_event(receipt_id: str, event_type: str, channel: str, responsible: str, note: str) -> None:
    events = _rows("receipt_events")
    events.append({
        "event_id": uuid4().hex[:12],
        "receipt_id": receipt_id,
        "event_type": event_type,
        "channel": channel,
        "responsible": responsible.strip() or "Sin asignar",
        "note": note.strip(),
        "created_at_utc": _now(),
    })
    _save("receipt_events", events)


def render_receipts_control() -> None:
    render_page_header(
        "Comprobantes",
        "Emite, entrega y audita comprobantes con historial de cada movimiento.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_receipts_plus()
    finally:
        base.render_page_header = original_header

    receipts = _rows("receipts_registry")
    payments = [item for item in _rows("payment_records") if not item.get("reversed")]
    sales = _rows("sales_registry")
    events = _rows("receipt_events")
    active = [item for item in receipts if item.get("status", "Emitido") != "Anulado"]
    delivered = [item for item in active if item.get("delivery_status") == "Entregado"]
    pending_delivery = [item for item in active if item.get("delivery_status") != "Entregado"]
    reprints = sum(int(_num(item.get("reprint_count"))) for item in receipts)

    st.divider()
    metrics = st.columns(4)
    metrics[0].metric("Pendientes de entrega", str(len(pending_delivery)))
    metrics[1].metric("Entregados", str(len(delivered)))
    metrics[2].metric("Reimpresiones", str(reprints))
    metrics[3].metric("Eventos", str(len(events)))

    incomplete = [
        item for item in payments
        if not str(item.get("sale_id", "")).strip()
        or _num(item.get("amount")) <= 0
        or not str(item.get("payment_method", item.get("method", ""))).strip()
    ]
    if incomplete:
        st.error(f"Hay {len(incomplete)} pago(s) con datos incompletos.")

    delivery_tab, bulk_tab, history_tab = st.tabs(("Entrega y reimpresión", "Emisión masiva", "Historial"))

    with delivery_tab:
        options = {
            f"{item.get('receipt_id', '')} · {format_money(_num(item.get('amount')))}": str(item.get("receipt_id", ""))
            for item in active
        }
        if not options:
            st.info("No hay comprobantes activos.")
        else:
            selected = st.selectbox("Comprobante", tuple(options.keys()), key="receipt_delivery_selected")
            receipt_id = options[selected]
            receipt = next(item for item in active if str(item.get("receipt_id", "")) == receipt_id)
            with st.form("receipt_delivery_form"):
                columns = st.columns(3)
                channel = columns[0].selectbox("Canal", ("WhatsApp", "Correo", "Impreso", "Presencial", "Otro"))
                responsible = columns[1].text_input("Responsable")
                delivered_now = columns[2].checkbox("Confirmar entrega", value=receipt.get("delivery_status") == "Entregado")
                note = st.text_input("Observación")
                save_delivery = st.form_submit_button("Guardar entrega", type="primary", use_container_width=True)
            if save_delivery:
                _update_receipt(receipt_id, {
                    "delivery_status": "Entregado" if delivered_now else "Pendiente",
                    "delivery_channel": channel,
                    "delivered_at_utc": _now() if delivered_now else "",
                })
                _add_event(receipt_id, "Entrega confirmada" if delivered_now else "Entrega pendiente", channel, responsible, note)
                st.rerun()

            if st.button("Registrar reimpresión", key=f"receipt_reprint_{receipt_id}", use_container_width=True):
                count = int(_num(receipt.get("reprint_count"))) + 1
                _update_receipt(receipt_id, {"reprint_count": count, "last_reprinted_at_utc": _now()})
                _add_event(receipt_id, "Reimpresión", "Impreso", "Sistema", f"Copia número {count}")
                st.rerun()

    with bulk_tab:
        pending_payments = [
            payment for payment in payments
            if str(payment.get("sale_id", "")).strip()
            and _num(payment.get("amount")) > 0
            and not any(
                str(receipt.get("payment_id", "")) == str(payment.get("payment_id", ""))
                and receipt.get("status", "Emitido") != "Anulado"
                for receipt in receipts
            )
        ]
        st.metric("Pagos listos", str(len(pending_payments)))
        if pending_payments and st.button("Emitir comprobantes pendientes", type="primary", use_container_width=True):
            updated = list(receipts)
            for payment in pending_payments:
                sale = next((item for item in sales if str(item.get("sale_id", "")) == str(payment.get("sale_id", ""))), {})
                updated.append({
                    "receipt_id": f"REC-{date.today().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
                    "payment_id": str(payment.get("payment_id", "")),
                    "sale_id": str(payment.get("sale_id", "")),
                    "issued_at_utc": _now(),
                    "amount": _num(payment.get("amount")),
                    "payment_method": str(payment.get("payment_method", payment.get("method", "Otro"))),
                    "reference": str(payment.get("reference", "")),
                    "concept": str(sale.get("description", "Pago de venta")),
                    "notes": "Emitido de forma masiva.",
                    "previous_paid": 0.0,
                    "status": "Emitido",
                    "delivery_status": "Pendiente",
                    "reprint_count": 0,
                })
            _save("receipts_registry", updated)
            st.rerun()
        elif not pending_payments:
            st.info("No hay pagos válidos pendientes de comprobante.")

    with history_tab:
        selected_filter = st.selectbox(
            "Filtrar",
            ("Todos", *[str(item.get("receipt_id", "")) for item in receipts]),
            key="receipt_event_filter",
        )
        visible = events if selected_filter == "Todos" else [item for item in events if str(item.get("receipt_id", "")) == selected_filter]
        if not visible:
            st.info("No hay movimientos registrados.")
        for event in reversed(visible[-100:]):
            with st.container(border=True):
                st.markdown(f"**{event.get('event_type', 'Evento')} · {event.get('receipt_id', '')}**")
                st.caption(f"{event.get('created_at_utc', '')} · {event.get('channel', '')} · {event.get('responsible', '')}")
                if event.get("note"):
                    st.write(str(event.get("note")))

    render_info_card(
        "Control documental",
        "Entregas y reimpresiones quedan incluidas en el respaldo general.",
        "COMPROBANTES",
    )
