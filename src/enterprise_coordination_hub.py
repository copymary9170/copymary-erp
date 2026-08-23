"""Coordinación transversal del ERP: agenda, notificaciones y documentos."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import streamlit as st

from src.session_utils import now_iso, read_list, save_list

TASKS_KEY = "enterprise_tasks"
DOCS_KEY = "enterprise_documents"
NOTIFICATION_ACK_KEY = "enterprise_notification_ack"

PRIORITIES = ("Baja", "Media", "Alta", "Urgente")
TASK_STATUS = ("Pendiente", "En progreso", "Hecha", "Cancelada")
DOC_TYPES = ("Legal", "Fiscal", "Cliente", "Proveedor", "Empleado", "Activo", "Contrato", "Garantía", "Comprobante", "Otro")


def _parse_date(value: str):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def task_notifications(tasks: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    result = []
    for row in tasks:
        if row.get("status") in ("Hecha", "Cancelada"):
            continue
        due = _parse_date(row.get("due_date", ""))
        if not due:
            continue
        days = (due - today).days
        if days < 0:
            result.append({"kind": "Tarea vencida", "severity": "Alta", "title": row.get("title", "Sin título"), "detail": f"Venció el {due.isoformat()}"})
        elif days <= int(row.get("reminder_days", 1) or 0):
            result.append({"kind": "Tarea próxima", "severity": "Media", "title": row.get("title", "Sin título"), "detail": f"Vence el {due.isoformat()}"})
    return result


def document_notifications(rows: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    result = []
    for row in rows:
        expiry = _parse_date(row.get("expiry_date", ""))
        if not expiry:
            continue
        days = (expiry - today).days
        warn = int(row.get("reminder_days", 30) or 0)
        if days < 0:
            result.append({"kind": "Documento vencido", "severity": "Alta", "title": row.get("name", "Documento"), "detail": f"Venció el {expiry.isoformat()}"})
        elif days <= warn:
            result.append({"kind": "Documento por vencer", "severity": "Media", "title": row.get("name", "Documento"), "detail": f"Vence el {expiry.isoformat()}"})
    return result


def collect_notifications() -> list[dict]:
    notices = [*task_notifications(read_list(TASKS_KEY)), *document_notifications(read_list(DOCS_KEY))]
    # Integra el calendario de Marketing cuando está disponible.
    try:
        from src import marketing_content_calendar as mcal
        for row in mcal.due_reminders(read_list(mcal.CALENDAR_KEY)):
            notices.append({"kind": "Marketing", "severity": "Media", "title": row.get("title", "Contenido"), "detail": f"Publicación {row.get('publication_date','')} {row.get('time','')} · {row.get('channel','')}"})
    except (ImportError, AttributeError):
        pass
    # Integra señales operativas ya existentes sin duplicar datos.
    try:
        from src import app_shell
        checks = (
            ("Cobros vencidos", getattr(app_shell, "_overdue_receivables", None), "Alta"),
            ("Compras por recibir", getattr(app_shell, "_pending_purchase_receipts", None), "Media"),
        )
        for label, fn, severity in checks:
            if callable(fn):
                count = int(fn() or 0)
                if count:
                    notices.append({"kind": label, "severity": severity, "title": f"{count} pendiente(s)", "detail": "Requiere revisión en su módulo correspondiente."})
        inv = getattr(app_shell, "_inventory_alert_counts", None)
        if callable(inv):
            low, expiring = inv()
            if low:
                notices.append({"kind": "Stock bajo", "severity": "Alta", "title": f"{int(low)} alerta(s)", "detail": "Revisa inventario y reposición."})
            if expiring:
                notices.append({"kind": "Lotes por vencer", "severity": "Media", "title": f"{int(expiring)} lote(s)", "detail": "Revisa vencimientos de inventario."})
    except ImportError:
        pass
    return notices


def render_agenda_tasks() -> None:
    st.markdown("# Agenda y tareas")
    st.caption("Un calendario operativo para compromisos que cruzan ventas, compras, producción, marketing y administración.")
    rows = read_list(TASKS_KEY)
    with st.form("enterprise_task", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        title = c1.text_input("Tarea")
        area = c2.text_input("Área / módulo", placeholder="Marketing, Compras, Producción...")
        priority = c3.selectbox("Prioridad", PRIORITIES, index=1)
        c1, c2, c3 = st.columns(3)
        due = c1.date_input("Fecha límite", date.today())
        status = c2.selectbox("Estado", TASK_STATUS)
        reminder = c3.number_input("Recordar con días de anticipación", min_value=0, max_value=365, value=1)
        owner = st.text_input("Responsable")
        notes = st.text_area("Notas / siguiente acción")
        if st.form_submit_button("Guardar tarea", type="primary", use_container_width=True) and title.strip():
            save_list(TASKS_KEY, [*rows, {"title": title.strip(), "area": area.strip(), "priority": priority, "due_date": due.isoformat(), "status": status, "reminder_days": int(reminder), "owner": owner.strip(), "notes": notes.strip(), "created_at_utc": now_iso()}])
            st.rerun()
    rows = read_list(TASKS_KEY)
    pending = [x for x in rows if x.get("status") not in ("Hecha", "Cancelada")]
    overdue = [x for x in pending if (_parse_date(x.get("due_date", "")) or date.max) < date.today()]
    c1, c2, c3 = st.columns(3); c1.metric("Pendientes", len(pending)); c2.metric("Vencidas", len(overdue)); c3.metric("Total", len(rows))
    if rows:
        st.dataframe(sorted(rows, key=lambda x: (x.get("due_date", ""), x.get("priority", ""))), use_container_width=True, hide_index=True)


def render_notification_center() -> None:
    st.markdown("# Centro de notificaciones")
    st.caption("Concentra alertas del ERP en un solo lugar; no crea copias de los datos originales.")
    notices = collect_notifications()
    high = sum(x.get("severity") == "Alta" for x in notices)
    medium = sum(x.get("severity") == "Media" for x in notices)
    c1, c2, c3 = st.columns(3); c1.metric("Alertas", len(notices)); c2.metric("Alta prioridad", high); c3.metric("Atención próxima", medium)
    if not notices:
        st.success("No hay alertas activas.")
        return
    for row in notices:
        with st.container(border=True):
            st.write(f"**{row.get('kind')} · {row.get('title')}**")
            st.caption(row.get("detail", ""))


def render_documents_center() -> None:
    st.markdown("# Documentos y archivos")
    st.caption("Índice documental del ERP. Guarda referencia, ubicación, responsable y vencimiento sin duplicar el archivo físico.")
    rows = read_list(DOCS_KEY)
    with st.form("enterprise_document", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Nombre del documento")
        doc_type = c2.selectbox("Tipo", DOC_TYPES)
        owner = c3.text_input("Responsable / relacionado")
        c1, c2 = st.columns(2)
        location = c1.text_input("Ruta, enlace o ubicación")
        expiry_enabled = c2.checkbox("Tiene vencimiento")
        c1, c2 = st.columns(2)
        expiry = c1.date_input("Fecha de vencimiento", date.today() + timedelta(days=365), disabled=not expiry_enabled)
        reminder = c2.number_input("Avisar antes (días)", min_value=0, max_value=365, value=30, disabled=not expiry_enabled)
        tags = st.text_input("Etiquetas", placeholder="rif, vehículo, contrato, garantía...")
        notes = st.text_area("Notas")
        if st.form_submit_button("Registrar documento", type="primary", use_container_width=True) and name.strip():
            save_list(DOCS_KEY, [*rows, {"name": name.strip(), "type": doc_type, "owner": owner.strip(), "location": location.strip(), "expiry_date": expiry.isoformat() if expiry_enabled else "", "reminder_days": int(reminder) if expiry_enabled else 0, "tags": tags.strip(), "notes": notes.strip(), "created_at_utc": now_iso()}])
            st.rerun()
    rows = read_list(DOCS_KEY)
    expiring = document_notifications(rows)
    c1, c2 = st.columns(2); c1.metric("Documentos", len(rows)); c2.metric("Alertas de vencimiento", len(expiring))
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)


def render_management_overview() -> None:
    st.markdown("# Resumen gerencial")
    st.caption("Vista transversal ligera para decidir qué requiere atención antes de abrir reportes especializados.")
    notices = collect_notifications(); tasks = read_list(TASKS_KEY); docs = read_list(DOCS_KEY)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Alertas activas", len(notices))
    c2.metric("Tareas pendientes", sum(x.get("status") not in ("Hecha", "Cancelada") for x in tasks))
    c3.metric("Documentos", len(docs))
    try:
        from src import marketing_content_calendar as mcal
        scheduled = sum(x.get("status") not in ("Publicado", "Cancelado") for x in read_list(mcal.CALENDAR_KEY))
    except (ImportError, AttributeError):
        scheduled = 0
    c4.metric("Contenido programado", scheduled)
    if notices:
        st.markdown("### Prioridades")
        for row in notices[:10]:
            st.write(f"**{row.get('kind')}** — {row.get('title')} · {row.get('detail','')}")
