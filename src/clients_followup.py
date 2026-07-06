"""Seguimiento comercial e historial de interacciones para clientes."""

from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src import session_backup
from src.clients_crm import render_clients_crm
from src.components import render_info_card, render_page_header


def _activate_backup() -> None:
    section = "customer_interactions"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Seguimiento de clientes"
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


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Cliente no disponible"


def _date_value(raw: str) -> date | None:
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _update_client_profile(client_id: str, tags: str, channel: str, priority: str) -> None:
    clients = _rows("customers_registry")
    updated = []
    for client in clients:
        current = dict(client)
        if str(current.get("client_id", "")) == client_id:
            current["commercial_tags"] = [item.strip() for item in tags.split(",") if item.strip()]
            current["preferred_channel"] = channel
            current["commercial_priority"] = priority
            current["updated_at_utc"] = _now()
        updated.append(current)
    _save("customers_registry", updated)


def _pending_followups(interactions: list[dict]) -> list[dict]:
    latest_by_interaction = {
        str(item.get("interaction_id", "")): item
        for item in interactions
        if item.get("next_followup") and item.get("status") != "Completado"
    }
    return sorted(
        latest_by_interaction.values(),
        key=lambda item: str(item.get("next_followup", "9999-12-31")),
    )


def render_clients_followup() -> None:
    render_page_header(
        "Clientes",
        "Fichas, segmentación, historial de contacto y próximas acciones comerciales en un solo lugar.",
    )

    original_header = render_clients_crm.__globals__["render_page_header"]
    render_clients_crm.__globals__["render_page_header"] = lambda *_args, **_kwargs: None
    try:
        render_clients_crm()
    finally:
        render_clients_crm.__globals__["render_page_header"] = original_header

    clients = _rows("customers_registry")
    interactions = _rows("customer_interactions")
    pending = _pending_followups(interactions)
    today = date.today()
    overdue = [item for item in pending if (_date_value(item.get("next_followup", "")) or today) < today]
    due_today = [item for item in pending if _date_value(item.get("next_followup", "")) == today]
    upcoming = [item for item in pending if (_date_value(item.get("next_followup", "")) or today) > today]

    st.divider()
    st.markdown("### Seguimiento comercial")
    metrics = st.columns(4)
    metrics[0].metric("Interacciones", str(len(interactions)))
    metrics[1].metric("Seguimientos vencidos", str(len(overdue)))
    metrics[2].metric("Para hoy", str(len(due_today)))
    metrics[3].metric("Próximos", str(len(upcoming)))

    if overdue:
        st.error(f"Hay {len(overdue)} seguimiento(s) vencido(s) que requieren atención.")
    elif due_today:
        st.warning(f"Hay {len(due_today)} seguimiento(s) programado(s) para hoy.")
    elif pending:
        st.info("No hay seguimientos vencidos; revisa las próximas acciones programadas.")
    else:
        st.success("No hay seguimientos comerciales pendientes.")

    if not clients:
        st.info("Registra al menos un cliente para usar el seguimiento comercial.")
        return

    client_options = {
        f"{client.get('name', 'Cliente')} · {client.get('client_id', '')}": str(client.get("client_id", ""))
        for client in clients
    }
    selected_label = st.selectbox("Cliente para gestionar", tuple(client_options.keys()), key="followup_client")
    selected_id = client_options[selected_label]
    selected_client = next(
        (client for client in clients if str(client.get("client_id", "")) == selected_id),
        {},
    )

    profile_tab, interaction_tab, agenda_tab = st.tabs(("Perfil comercial", "Registrar interacción", "Agenda de seguimiento"))

    with profile_tab:
        with st.form("client_commercial_profile"):
            tags = st.text_input(
                "Etiquetas comerciales",
                value=", ".join(str(item) for item in selected_client.get("commercial_tags", [])),
                placeholder="Ejemplo: escolar, empresa, sublimación, frecuente",
            )
            columns = st.columns(2)
            channel_options = ("WhatsApp", "Llamada", "Correo", "Instagram", "Presencial", "Otro")
            current_channel = str(selected_client.get("preferred_channel", "WhatsApp"))
            if current_channel not in channel_options:
                current_channel = "WhatsApp"
            channel = columns[0].selectbox(
                "Canal preferido",
                channel_options,
                index=channel_options.index(current_channel),
            )
            priority_options = ("Normal", "Alta", "VIP", "Baja")
            current_priority = str(selected_client.get("commercial_priority", "Normal"))
            if current_priority not in priority_options:
                current_priority = "Normal"
            priority = columns[1].selectbox(
                "Prioridad comercial",
                priority_options,
                index=priority_options.index(current_priority),
            )
            save_profile = st.form_submit_button("Guardar perfil comercial", use_container_width=True)
        if save_profile:
            _update_client_profile(selected_id, tags, channel, priority)
            st.success("Perfil comercial actualizado.")
            st.rerun()

        render_info_card(
            "Preferencias del cliente",
            f"Canal: {current_channel} · Prioridad: {current_priority} · Etiquetas: {tags or 'Sin etiquetas'}",
            "PERFIL COMERCIAL",
        )

    with interaction_tab:
        with st.form("customer_interaction_form", clear_on_submit=True):
            first = st.columns(3)
            interaction_type = first[0].selectbox(
                "Tipo de contacto",
                ("WhatsApp", "Llamada", "Correo", "Instagram", "Visita", "Otro"),
            )
            outcome = first[1].selectbox(
                "Resultado",
                ("Interesado", "Pendiente de respuesta", "Cotización enviada", "Venta lograda", "No interesado", "Otro"),
            )
            owner = first[2].text_input("Responsable", placeholder="Mary")
            summary = st.text_area("Resumen de la conversación", max_chars=700)
            second = st.columns(2)
            next_followup = second[0].date_input("Próximo seguimiento", value=date.today())
            next_action = second[1].text_input("Próxima acción", placeholder="Enviar catálogo, llamar, confirmar pago...")
            submitted = st.form_submit_button("Guardar interacción", type="primary", use_container_width=True)
        if submitted:
            if not summary.strip():
                st.error("Escribe un resumen de la interacción.")
            else:
                interactions.append(
                    {
                        "interaction_id": uuid4().hex[:12],
                        "client_id": selected_id,
                        "created_at_utc": _now(),
                        "interaction_type": interaction_type,
                        "outcome": outcome,
                        "owner": owner.strip() or "Sin asignar",
                        "summary": summary.strip(),
                        "next_followup": next_followup.isoformat(),
                        "next_action": next_action.strip(),
                        "status": "Pendiente",
                    }
                )
                _save("customer_interactions", interactions)
                st.success("Interacción guardada.")
                st.rerun()

        client_history = [
            item for item in interactions if str(item.get("client_id", "")) == selected_id
        ]
        st.markdown("#### Historial del cliente")
        if not client_history:
            st.info("Este cliente todavía no tiene interacciones registradas.")
        for item in reversed(client_history):
            with st.container(border=True):
                columns = st.columns([3, 1])
                with columns[0]:
                    st.markdown(f"**{item.get('interaction_type', 'Contacto')} · {item.get('outcome', '')}**")
                    st.write(str(item.get("summary", "")))
                    st.caption(
                        f"Responsable: {item.get('owner', 'Sin asignar')} · "
                        f"Próxima acción: {item.get('next_action') or 'No indicada'} · "
                        f"Fecha: {item.get('next_followup') or 'Sin fecha'}"
                    )
                columns[1].metric("Estado", str(item.get("status", "Pendiente")))

    with agenda_tab:
        status_filter = st.selectbox(
            "Mostrar",
            ("Todos", "Vencidos", "Hoy", "Próximos"),
            key="followup_status_filter",
        )
        visible = pending
        if status_filter == "Vencidos":
            visible = overdue
        elif status_filter == "Hoy":
            visible = due_today
        elif status_filter == "Próximos":
            visible = upcoming

        if not visible:
            st.info("No hay seguimientos en esta categoría.")
        for item in visible:
            interaction_id = str(item.get("interaction_id", ""))
            followup_date = _date_value(item.get("next_followup", ""))
            is_overdue = bool(followup_date and followup_date < today)
            with st.container(border=True):
                columns = st.columns([3, 1, 1])
                with columns[0]:
                    st.markdown(f"#### {_client_name(str(item.get('client_id', '')), clients)}")
                    st.write(str(item.get("next_action") or item.get("summary", "")))
                    st.caption(
                        f"Fecha: {item.get('next_followup', 'Sin fecha')} · "
                        f"Responsable: {item.get('owner', 'Sin asignar')} · "
                        f"Resultado previo: {item.get('outcome', '')}"
                    )
                columns[1].metric("Prioridad", "Vencido" if is_overdue else "Programado")
                if columns[2].button(
                    "Completar",
                    key=f"complete_followup_{interaction_id}",
                    use_container_width=True,
                    type="primary" if is_overdue else "secondary",
                ):
                    updated = []
                    for current in interactions:
                        row = dict(current)
                        if str(row.get("interaction_id", "")) == interaction_id:
                            row["status"] = "Completado"
                            row["completed_at_utc"] = _now()
                        updated.append(row)
                    _save("customer_interactions", updated)
                    st.rerun()

    render_info_card(
        "Seguimiento respaldado",
        "Las interacciones, responsables y próximas acciones se incluyen en el respaldo general de la sesión.",
        "HISTORIAL COMERCIAL",
    )
