"""Seguimiento comercial y plantillas para cotizaciones."""

from collections import Counter
from datetime import date
from uuid import uuid4

import streamlit as st

from src import quotes_manager as base, session_backup
from src.components import render_info_card, render_page_header
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (("quote_followups", "Seguimiento de cotizaciones"), ("quote_templates", "Plantillas de cotización")):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _quote_label(quote: dict, clients: list[dict]) -> str:
    client_id = str(quote.get("client_id", ""))
    client = next((str(item.get("name", "Cliente")) for item in clients if str(item.get("client_id", "")) == client_id), "Sin cliente")
    return f"{quote.get('title') or 'Cotización'} · {quote.get('quote_id', '')} · {client}"


def _update_quote(quote_id: str, updates: dict) -> None:
    quotes = _rows("quotes_registry")
    for quote in quotes:
        if str(quote.get("quote_id", "")) == quote_id:
            quote.update(updates)
            quote["updated_at_utc"] = _now()
    _save("quotes_registry", quotes)


def render_quotes_followup() -> None:
    render_page_header("Cotizaciones", "Propuestas, recordatorios y resultados comerciales en un solo flujo.")
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_quotes_manager()
    finally:
        base.render_page_header = original_header

    clients = _rows("customers_registry")
    quotes = _rows("quotes_registry")
    followups = _rows("quote_followups")
    templates = _rows("quote_templates")
    today = date.today()
    pending = [item for item in followups if item.get("status") != "Completado" and item.get("followup_date")]
    pending.sort(key=lambda item: str(item.get("followup_date", "9999-12-31")))
    overdue = [item for item in pending if (_as_date(item.get("followup_date")) or today) < today]
    due_today = [item for item in pending if _as_date(item.get("followup_date")) == today]

    st.divider()
    metrics = st.columns(4)
    metrics[0].metric("Seguimientos", str(len(pending)))
    metrics[1].metric("Vencidos", str(len(overdue)))
    metrics[2].metric("Para hoy", str(len(due_today)))
    metrics[3].metric("Plantillas", str(len(templates)))

    active = [quote for quote in quotes if str(quote.get("status", "")) not in {"Convertida", "Rechazada"}]
    options = {_quote_label(quote, clients): str(quote.get("quote_id", "")) for quote in active}
    follow_tab, agenda_tab, result_tab, template_tab = st.tabs(("Seguimiento", "Agenda", "Resultados", "Plantillas"))

    with follow_tab:
        if not options:
            st.info("No hay cotizaciones activas.")
        else:
            with st.form("quote_followup_form", clear_on_submit=True):
                selected = st.selectbox("Cotización", tuple(options.keys()))
                columns = st.columns(3)
                channel = columns[0].selectbox("Canal", ("WhatsApp", "Llamada", "Correo", "Presencial", "Otro"))
                responsible = columns[1].text_input("Responsable")
                followup_date = columns[2].date_input("Próximo seguimiento", value=today)
                note = st.text_area("Resumen del contacto", max_chars=700)
                next_action = st.text_input("Próxima acción")
                submitted = st.form_submit_button("Guardar seguimiento", type="primary", use_container_width=True)
            if submitted:
                if not note.strip():
                    st.error("Escribe un resumen del contacto.")
                else:
                    followups.append({"followup_id": uuid4().hex[:12], "quote_id": options[selected], "created_at_utc": _now(), "channel": channel, "responsible": responsible.strip() or "Sin asignar", "note": note.strip(), "next_action": next_action.strip(), "followup_date": followup_date.isoformat(), "status": "Pendiente"})
                    _save("quote_followups", followups)
                    _update_quote(options[selected], {"status": "En seguimiento"})
                    st.rerun()

    with agenda_tab:
        if not pending:
            st.info("No hay seguimientos pendientes.")
        for item in pending:
            quote = next((row for row in quotes if str(row.get("quote_id", "")) == str(item.get("quote_id", ""))), {})
            title = str(quote.get("title") or f"Cotización {item.get('quote_id', '')}")
            followup_id = str(item.get("followup_id", ""))
            is_overdue = bool(_as_date(item.get("followup_date")) and _as_date(item.get("followup_date")) < today)
            with st.container(border=True):
                columns = st.columns([3, 1, 1])
                columns[0].markdown(f"#### {title}")
                columns[0].write(str(item.get("next_action") or item.get("note", "")))
                columns[0].caption(f"{item.get('responsible', 'Sin asignar')} · {item.get('followup_date', '')}")
                columns[1].metric("Estado", "Vencido" if is_overdue else "Programado")
                if columns[2].button("Completar", key=f"finish_quote_followup_{followup_id}", use_container_width=True):
                    for record in followups:
                        if str(record.get("followup_id", "")) == followup_id:
                            record["status"] = "Completado"
                            record["completed_at_utc"] = _now()
                    _save("quote_followups", followups)
                    st.rerun()

    with result_tab:
        closeable = [quote for quote in quotes if str(quote.get("status", "")) != "Convertida"]
        close_options = {_quote_label(quote, clients): str(quote.get("quote_id", "")) for quote in closeable}
        if close_options:
            with st.form("quote_result_form"):
                selected = st.selectbox("Cotización", tuple(close_options.keys()), key="quote_result_quote")
                outcome = st.selectbox("Resultado", ("Aceptada", "Rechazada"))
                reason = st.selectbox("Motivo", ("Precio", "Tiempo de entrega", "Compra aplazada", "Competencia", "Condiciones", "Sin respuesta", "Otro"))
                detail = st.text_area("Detalle", max_chars=500)
                save_result = st.form_submit_button("Registrar resultado", use_container_width=True)
            if save_result:
                _update_quote(close_options[selected], {"status": outcome, "outcome_reason": reason, "outcome_details": detail.strip(), "outcome_at_utc": _now()})
                st.rerun()
        rejected = [quote for quote in quotes if str(quote.get("status", "")) == "Rechazada"]
        won = [quote for quote in quotes if quote.get("converted_sale_id")]
        cards = st.columns(3)
        cards[0].metric("Ganadas", str(len(won)))
        cards[1].metric("Rechazadas", str(len(rejected)))
        cards[2].metric("Tasa de cierre", f"{len(won) / (len(won) + len(rejected)) * 100:,.1f}%" if won or rejected else "0.0%")
        for reason, count in Counter(str(quote.get("outcome_reason", "Sin motivo")) for quote in rejected).most_common():
            st.write(f"**{reason}:** {count}")

    with template_tab:
        with st.form("quote_template_form", clear_on_submit=True):
            name = st.text_input("Nombre de la plantilla")
            items = st.text_area("Conceptos sugeridos", placeholder="Un concepto por línea")
            terms = st.text_area("Condiciones predeterminadas")
            save_template = st.form_submit_button("Guardar plantilla", type="primary", use_container_width=True)
        if save_template:
            if not name.strip():
                st.error("Escribe un nombre para la plantilla.")
            else:
                templates.append({"template_id": uuid4().hex[:12], "name": name.strip(), "item_suggestions": [line.strip() for line in items.splitlines() if line.strip()], "terms": terms.strip(), "created_at_utc": _now()})
                _save("quote_templates", templates)
                st.rerun()
        for template in templates:
            with st.container(border=True):
                columns = st.columns([3, 1])
                columns[0].markdown(f"#### {template.get('name', 'Plantilla')}")
                columns[0].write(" · ".join(str(item) for item in template.get("item_suggestions", [])) or "Sin conceptos")
                if columns[1].button("Eliminar", key=f"delete_quote_template_{template.get('template_id', '')}", use_container_width=True):
                    _save("quote_templates", [item for item in templates if item.get("template_id") != template.get("template_id")])
                    st.rerun()

    render_info_card("Seguimiento respaldado", "Recordatorios, resultados y plantillas se incluyen en el respaldo general.", "CICLO DE COTIZACIÓN")
