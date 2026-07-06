"""Seguimiento, recordatorios y plantillas para cotizaciones."""

from collections import Counter
from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src import quotes_manager as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money


def _activate_backup() -> None:
    for section, label in (
        ("quote_followups", "Seguimiento de cotizaciones"),
        ("quote_templates", "Plantillas de cotización"),
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


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date(raw) -> date | None:
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _quote_total(quote: dict) -> float:
    subtotal = sum(
        _number(item.get("quantity")) * _number(item.get("unit_price"))
        for item in quote.get("items", [])
        if isinstance(item, dict)
    )
    return max(subtotal - _number(quote.get("discount")), 0.0)


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _update_quote(quote_id: str, updates: dict) -> None:
    quotes = _rows("quotes_registry")
    changed = []
    for quote in quotes:
        current = dict(quote)
        if str(current.get("quote_id", "")) == quote_id:
            current.update(updates)
            current["updated_at_utc"] = _now()
        changed.append(current)
    _save("quotes_registry", changed)


def _pending_followups(records: list[dict]) -> list[dict]:
    return sorted(
        [item for item in records if item.get("status") != "Completado" and item.get("followup_date")],
        key=lambda item: str(item.get("followup_date", "9999-12-31")),
    )


def render_quotes_followup() -> None:
    render_page_header(
        "Cotizaciones",
        "Crea propuestas, controla su vigencia y organiza el seguimiento hasta ganar o cerrar cada oportunidad.",
    )

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

    pending = _pending_followups(followups)
    overdue = [item for item in pending if (_date(item.get("followup_date")) or today) < today]
    due_today = [item for item in pending if _date(item.get("followup_date")) == today]
    upcoming = [item for item in pending if (_date(item.get("followup_date")) or today) > today]

    st.divider()
    st.markdown("### Seguimiento de oportunidades")
    metrics = st.columns(4)
    metrics[0].metric("Seguimientos pendientes", str(len(pending)))
    metrics[1].metric("Vencidos", str(len(overdue)))
    metrics[2].metric("Para hoy", str(len(due_today)))
    metrics[3].metric("Plantillas", str(len(templates)))

    if overdue:
        st.error(f"Hay {len(overdue)} seguimiento(s) vencido(s).")
    elif due_today:
        st.warning(f"Hay {len(due_today)} seguimiento(s) para hoy.")
    elif pending:
        st.info("Los seguimientos pendientes están dentro de fecha.")
    else:
        st.success("No hay seguimientos pendientes.")

    active_quotes = [
        quote for quote in quotes
        if str(quote.get("status", "Borrador")) not in {"Convertida", "Rechazada"}
    ]
    quote_options = {
        f"{quote.get('title') or 'Cotización'} · {quote.get('quote_id', '')} · {_client_name(str(quote.get('client_id', '')), clients)}": str(quote.get("quote_id", ""))
        for quote in active_quotes
    }

    follow_tab, agenda_tab, outcome_tab, template_tab = st.tabs(
        ("Registrar seguimiento", "Agenda", "Ganadas y perdidas", "Plantillas")
    )

    with follow_tab:
        if not quote_options:
            st.info("No hay cotizaciones activas disponibles para seguimiento.")
        else:
            with st.form("quote_followup_form", clear_on_submit=True):
                selected_label = st.selectbox("Cotización", tuple(quote_options.keys()))
                columns = st.columns(3)
                channel = columns[0].selectbox("Canal", ("WhatsApp", "Llamada", "Correo", "Presencial", "Otro"))
                responsible = columns[1].text_input("Responsable", placeholder="Mary")
                followup_date = columns[2].date_input("Próximo seguimiento", value=today)
                result = st.selectbox(
                    "Resultado del contacto",
                    ("Pendiente de respuesta", "Cliente interesado", "Solicitó cambios", "Negociando", "Sin respuesta", "Otro"),
                )
                note = st.text_area("Resumen del contacto", max_chars=700)
                next_action = st.text_input("Próxima acción", placeholder="Llamar, enviar versión corregida, confirmar aceptación...")
                submitted = st.form_submit_button("Guardar seguimiento", type="primary", use_container_width=True)
            if submitted:
                if not note.strip():
                    st.error("Escribe un resumen del contacto.")
                else:
                    followups.append({
                        "followup_id": uuid4().hex[:12],
                        "quote_id": quote_options[selected_label],
                        "created_at_utc": _now(),
                        "channel": channel,
                        "responsible": responsible.strip() or "Sin asignar",
                        "result": result,
                        "note": note.strip(),
                        "next_action": next_action.strip(),
                        "followup_date": followup_date.isoformat(),
                        "status": "Pendiente",
                    })
                    _save("quote_followups", followups)
                    _update_quote(quote_options[selected_label], {"status": "En seguimiento"})
                    st.rerun()

    with agenda_tab:
        filter_value = st.selectbox("Mostrar", ("Todos", "Vencidos", "Hoy", "Próximos"), key="quote_followup_filter")
        visible = pending
        if filter_value == "Vencidos":
            visible = overdue
        elif filter_value == "Hoy":
            visible = due_today
        elif filter_value == "Próximos":
            visible = upcoming

        if not visible:
            st.info("No hay seguimientos en esta categoría.")
        for item in visible:
            quote = next((row for row in quotes if str(row.get("quote_id", "")) == str(item.get("quote_id", ""))), {})
            followup_id = str(item.get("followup_id", ""))
            scheduled = _date(item.get("followup_date"))
            is_overdue = bool(scheduled and scheduled < today)
            with st.container(border=True):
                columns = st.columns([3, 1, 1])
                columns[0].markdown(f"#### {quote.get('title') or f'Cotización {item.get("quote_id", "")}' }")
                columns[0].write(str(item.get("next_action") or item.get("note", "")))
                columns[0].caption(
                    f"{item.get('channel', '')} · Responsable: {item.get('responsible', 'Sin asignar')} · "
                    f"Fecha: {item.get('followup_date', '')}"
                )
                columns[1].metric("Estado", "Vencido" if is_overdue else "Programado")
                if columns[2].button("Completar", key=f"complete_quote_followup_{followup_id}", use_container_width=True, type="primary" if is_overdue else "secondary"):
                    updated = []
                    for record in followups:
                        current = dict(record)
                        if str(current.get("followup_id", "")) == followup_id:
                            current["status"] = "Completado"
                            current["completed_at_utc"] = _now()
                        updated.append(current)
                    _save("quote_followups", updated)
                    st.rerun()

    with outcome_tab:
        closed_options = {
            f"{quote.get('title') or 'Cotización'} · {quote.get('quote_id', '')}": str(quote.get("quote_id", ""))
            for quote in quotes
            if str(quote.get("status", "Borrador")) not in {"Convertida"}
        }
        if closed_options:
            with st.form("quote_outcome_form"):
                selected = st.selectbox("Cotización", tuple(closed_options.keys()), key="quote_outcome_quote")
                outcome = st.selectbox("Resultado", ("Aceptada", "Rechazada"))
                reason = st.selectbox(
                    "Motivo",
                    ("Precio", "Tiempo de entrega", "Cliente aplazó la compra", "Eligió otra opción", "Condiciones", "Sin respuesta", "Otro"),
                )
                details = st.text_area("Detalle", max_chars=500)
                save_outcome = st.form_submit_button("Registrar resultado", use_container_width=True)
            if save_outcome:
                updates = {
                    "status": outcome,
                    "outcome_reason": reason,
                    "outcome_details": details.strip(),
                    "outcome_at_utc": _now(),
                }
                _update_quote(closed_options[selected], updates)
                st.rerun()

        rejected = [quote for quote in quotes if str(quote.get("status", "")) == "Rechazada"]
        converted = [quote for quote in quotes if quote.get("converted_sale_id")]
        analysis = st.columns(3)
        analysis[0].metric("Ganadas", str(len(converted)))
        analysis[1].metric("Rechazadas", str(len(rejected)))
        analysis[2].metric(
            "Tasa de cierre",
            f"{len(converted) / (len(converted) + len(rejected)) * 100:,.1f}%" if converted or rejected else "0.0%",
        )
        reasons = Counter(str(quote.get("outcome_reason", "Sin motivo")) for quote in rejected)
        if reasons:
            st.markdown("#### Motivos de rechazo")
            for reason, count in reasons.most_common():
                st.write(f"**{reason}:** {count}")

    with template_tab:
        with st.form("quote_template_form", clear_on_submit=True):
            template_name = st.text_input("Nombre de la plantilla", placeholder="Ejemplo: Kit escolar básico")
            columns = st.columns(3)
            default_validity = columns[0].number_input("Vigencia predeterminada", min_value=1, value=7, step=1)
            default_discount = columns[1].number_input("Descuento predeterminado", min_value=0.0, value=0.0, step=0.5)
            default_deposit = columns[2].number_input("Anticipo predeterminado", min_value=0.0, value=0.0, step=0.5)
            template_items = st.text_area(
                "Conceptos de referencia",
                placeholder="Una línea por concepto. Ejemplo:\nImpresión a color\nCarpeta personalizada",
            )
            template_terms = st.text_area("Condiciones predeterminadas", max_chars=700)
            save_template = st.form_submit_button("Guardar plantilla", type="primary", use_container_width=True)
        if save_template:
            if not template_name.strip():
                st.error("Escribe un nombre para la plantilla.")
            else:
                templates.append({
                    "template_id": uuid4().hex[:12],
                    "name": template_name.strip(),
                    "validity_days": int(default_validity),
                    "discount": float(default_discount),
                    "deposit_required": float(default_deposit),
                    "item_suggestions": [line.strip() for line in template_items.splitlines() if line.strip()],
                    "terms": template_terms.strip(),
                    "created_at_utc": _now(),
                })
                _save("quote_templates", templates)
                st.rerun()

        if not templates:
            st.info("Todavía no hay plantillas guardadas.")
        for template in templates:
            with st.container(border=True):
                columns = st.columns([3, 1])
                columns[0].markdown(f"#### {template.get('name', 'Plantilla')}")
                columns[0].caption(
                    f"Vigencia {template.get('validity_days', 7)} días · "
                    f"Descuento {format_money(_number(template.get('discount')))} · "
                    f"Anticipo {format_money(_number(template.get('deposit_required')))}"
                )
                if template.get("item_suggestions"):
                    columns[0].write(" · ".join(str(item) for item in template.get("item_suggestions", [])))
                if columns[1].button("Eliminar", key=f"delete_quote_template_{template.get('template_id', '')}", use_container_width=True):
                    _save("quote_templates", [item for item in templates if item.get("template_id") != template.get("template_id")])
                    st.rerun()

    render_info_card(
        "Seguimiento respaldado",
        "Recordatorios, motivos de cierre y plantillas quedan incluidos en el respaldo general.",
        "CICLO DE COTIZACIÓN",
    )
