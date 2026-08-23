"""Calendario editorial y recordatorios internos para Marketing Workspace."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import calendar

import streamlit as st

from src.session_utils import now_iso, read_list, save_list

CALENDAR_KEY = "marketing_content_calendar"
REMINDER_OPTIONS = ("Sin recordatorio", "El mismo día", "1 día antes", "2 días antes", "3 días antes", "7 días antes")
REMINDER_DAYS = {"Sin recordatorio": None, "El mismo día": 0, "1 día antes": 1, "2 días antes": 2, "3 días antes": 3, "7 días antes": 7}


def reminder_date(publication_date: str, reminder: str):
    days = REMINDER_DAYS.get(reminder)
    if days is None or not publication_date:
        return None
    return date.fromisoformat(publication_date) - timedelta(days=days)


def due_reminders(rows: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    due = []
    for row in rows:
        if row.get("status") in ("Publicado", "Cancelado") or row.get("reminder_done"):
            continue
        remind_on = reminder_date(row.get("publication_date", ""), row.get("reminder", "Sin recordatorio"))
        if remind_on and remind_on <= today:
            due.append(row)
    return due


def _month_grid(rows: list[dict]) -> None:
    today = date.today()
    c1, c2 = st.columns(2)
    year = c1.number_input("Año", min_value=2020, max_value=2100, value=today.year, step=1)
    month = c2.selectbox("Mes", range(1, 13), index=today.month - 1, format_func=lambda m: calendar.month_name[m].capitalize())
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(int(year), int(month))
    st.markdown(f"#### {calendar.month_name[int(month)].capitalize()} {int(year)}")
    headers = st.columns(7)
    for col, label in zip(headers, ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")):
        col.markdown(f"**{label}**")
    for week in weeks:
        cols = st.columns(7)
        for col, day in zip(cols, week):
            if not day:
                col.write(" ")
                continue
            current = date(int(year), int(month), day)
            items = [x for x in rows if x.get("publication_date") == current.isoformat()]
            with col.container(border=True):
                st.markdown(f"**{day}**")
                for item in items[:4]:
                    st.caption(f"{item.get('time','')} · {item.get('title','Sin título')}")
                    st.caption(f"{item.get('channel','')} · {item.get('status','Programado')}")
                if len(items) > 4:
                    st.caption(f"+{len(items)-4} más")


def render_content_calendar(content_rows: list[dict] | None = None) -> None:
    st.subheader("Calendario de contenido")
    st.caption("Programa qué publicar, cuándo hacerlo y cuándo quieres que el ERP te lo recuerde.")
    rows = read_list(CALENDAR_KEY)
    content_rows = content_rows or []
    titles = [x.get("title", "") for x in content_rows if x.get("title")]

    due = due_reminders(rows)
    if due:
        st.error(f"🔔 Tienes {len(due)} recordatorio(s) de contenido pendiente(s).")
        for item in due[:5]:
            st.warning(f"{item.get('publication_date')} {item.get('time','')} · {item.get('title','Sin título')} · {item.get('channel','')}")

    tabs = st.tabs(("Calendario", "Programar", "Agenda", "Recordatorios"))
    with tabs[0]:
        _month_grid(rows)

    with tabs[1]:
        with st.form("marketing_schedule_content", clear_on_submit=True):
            c1, c2 = st.columns(2)
            title = c1.selectbox("Pieza de Content Studio", ["Nueva / no vinculada", *titles])
            custom_title = c2.text_input("Título", disabled=title != "Nueva / no vinculada")
            c1, c2, c3 = st.columns(3)
            publication = c1.date_input("Fecha de publicación", date.today())
            time_value = c2.time_input("Hora", datetime.now().replace(second=0, microsecond=0).time())
            channel = c3.selectbox("Canal", ("Instagram", "TikTok", "Facebook", "YouTube", "Email", "WhatsApp", "Otro"))
            c1, c2 = st.columns(2)
            reminder = c1.selectbox("Recordarme", REMINDER_OPTIONS, index=2)
            status = c2.selectbox("Estado", ("Programado", "Preparando", "Listo", "Publicado", "Cancelado"))
            notes = st.text_area("Notas / instrucciones")
            if st.form_submit_button("Agregar al calendario", type="primary", use_container_width=True):
                final_title = custom_title.strip() if title == "Nueva / no vinculada" else title
                if final_title:
                    save_list(CALENDAR_KEY, [*rows, {
                        "title": final_title, "publication_date": publication.isoformat(),
                        "time": time_value.strftime("%H:%M"), "channel": channel, "reminder": reminder,
                        "status": status, "notes": notes.strip(), "reminder_done": False,
                        "created_at_utc": now_iso(),
                    }])
                    st.rerun()

    with tabs[2]:
        upcoming = sorted([x for x in rows if x.get("status") not in ("Publicado", "Cancelado")], key=lambda x: (x.get("publication_date", ""), x.get("time", "")))
        if upcoming:
            st.dataframe(upcoming, use_container_width=True, hide_index=True)
        else:
            st.info("No hay contenido pendiente programado.")

    with tabs[3]:
        if not due:
            st.success("No tienes recordatorios vencidos o para hoy.")
        for item in due:
            st.markdown(f"**{item.get('title','Sin título')}** · {item.get('publication_date')} {item.get('time','')}")
            st.caption(f"{item.get('channel','')} · Recordatorio: {item.get('reminder','')}")
        st.caption("Estos avisos aparecen dentro del ERP cuando entras a Marketing. Para avisos aunque el ERP esté cerrado se necesita un servicio externo de notificaciones.")
