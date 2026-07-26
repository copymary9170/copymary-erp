"""Centro de actualizaciones, adopción y seguimiento de CopyMary ERP."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from src import app_shell, auth, session_backup
from src.config import APP_VERSION, PROJECT_STATUS
from src.session_utils import now_iso, read_list, save_list


WHATS_NEW = (
    {
        "id": "inicio-navegacion-20260726",
        "version": "2026.07.26",
        "title": "Inicio y navegación reparados",
        "summary": "Se corrigieron accesos inválidos, paneles sustituidos y páginas duplicadas de Streamlit.",
        "category": "Experiencia",
        "change_type": "Corrección",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "Inicio",
        "audience": "Todo el equipo",
        "requires_action": False,
        "action": "Revisa que tus accesos habituales aparezcan en el área correcta.",
        "details": (
            "Panel comercial y panel financiero vuelven a ser independientes.",
            "El tablero ejecutivo conserva una entrada propia.",
            "Catálogo y recepción dejaron de mostrarse como páginas duplicadas.",
        ),
    },
    {
        "id": "catalogo-inventario-20260726",
        "version": "2026.07.26",
        "title": "Catálogo integrado en Inventario",
        "summary": "La ficha técnica de artículos se incorporó al flujo de Inventario para evitar módulos aislados.",
        "category": "Inventario",
        "change_type": "Mejora",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "Inventario",
        "audience": "Inventario y producción",
        "requires_action": True,
        "action": "Completa las fichas técnicas de los materiales que todavía no tengan medidas o gramaje.",
        "details": (
            "Medidas reales de los cuatro lados y área utilizable.",
            "Gramaje, peso, volumen y calidad del corte.",
            "Migración segura de artículos existentes.",
        ),
    },
    {
        "id": "recepcion-compras-20260726",
        "version": "2026.07.26",
        "title": "Recepción integrada en Compras",
        "summary": "La recepción parcial de mercancía ahora forma parte del ciclo completo de abastecimiento.",
        "category": "Compras",
        "change_type": "Mejora",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "Compras",
        "audience": "Compras y almacén",
        "requires_action": True,
        "action": "Revisa las compras abiertas y registra las cantidades que ya fueron recibidas.",
        "details": (
            "Recepciones parciales y cantidades pendientes.",
            "Condición, responsable y observaciones de recepción.",
            "Seguimiento conjunto de pedido, recepción y pago.",
        ),
    },
    {
        "id": "tablero-ejecutivo-20260726",
        "version": "2026.07.26",
        "title": "Tablero ejecutivo real",
        "summary": "Indicadores de ventas, margen, clientes, entregas, capacidad, mermas y aprobaciones.",
        "category": "Analítica",
        "change_type": "Nuevo módulo",
        "status": "Disponible",
        "impact": "Media",
        "date": "2026-07-26",
        "target": "Tablero ejecutivo",
        "audience": "Dirección y administración",
        "requires_action": False,
        "action": "Úsalo al cierre de semana para revisar rentabilidad y atrasos.",
        "details": (
            "Rentabilidad por producto o servicio.",
            "Comparación contra el período anterior.",
            "Trazabilidad de aprobaciones y cambios.",
        ),
    },
    {
        "id": "rrhh-laboral-20260726",
        "version": "2026.07.26",
        "title": "Control laboral venezolano",
        "summary": "Expedientes, asistencia, vacaciones, prestaciones y recibos de pago dentro de RRHH.",
        "category": "Talento humano",
        "change_type": "Nuevo módulo",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "RRHH y nómina",
        "audience": "Administración y RRHH",
        "requires_action": True,
        "action": "Registra los expedientes y parámetros laborales antes de generar recibos.",
        "details": (
            "Gestión de asistencia y ausencias.",
            "Cálculos referenciales de vacaciones y prestaciones.",
            "Recibos de pago exportables.",
        ),
    },
    {
        "id": "cumplimiento-legal-20260726",
        "version": "2026.07.26",
        "title": "Cumplimiento fiscal y documental",
        "summary": "Validaciones fiscales, contratos y retención inalterable de documentos legales.",
        "category": "Legal",
        "change_type": "Seguridad",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "Comprobantes",
        "audience": "Administración y contabilidad",
        "requires_action": True,
        "action": "Configura los datos fiscales y valida el medio autorizado antes de emitir documentos reales.",
        "details": (
            "Validación de datos fiscales obligatorios.",
            "Contratos y términos editables.",
            "Cadena de integridad para detectar alteraciones.",
        ),
    },
    {
        "id": "tasas-comisiones-20260724",
        "version": "2026.07.24",
        "title": "Tasas, IVA, IGTF y comisiones conectadas",
        "summary": "Las ventas usan la configuración monetaria vigente y conservan el neto realmente recibido.",
        "category": "Finanzas",
        "change_type": "Mejora",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-24",
        "target": "Configuración General",
        "audience": "Ventas y administración",
        "requires_action": True,
        "action": "Confirma diariamente las tasas y revisa las comisiones de cada medio de pago.",
        "details": (
            "IVA manual por venta.",
            "Comisiones e IGTF aplicados sobre el monto procesado.",
            "Historial de tasas y aviso cuando están desactualizadas.",
        ),
    },
    {
        "id": "postgresql-externo-20260724",
        "version": "2026.07.24",
        "title": "Persistencia con PostgreSQL externo",
        "summary": "El ERP puede conservar datos fuera del disco efímero de Streamlit Cloud.",
        "category": "Infraestructura",
        "change_type": "Infraestructura",
        "status": "Requiere configuración",
        "impact": "Alta",
        "date": "2026-07-24",
        "target": None,
        "audience": "Administración técnica",
        "requires_action": True,
        "action": "Configura COPYMARY_DATABASE_URL o el Secret equivalente antes de depender del despliegue en producción.",
        "details": (
            "Compatible con COPYMARY_DATABASE_URL y Secrets de Streamlit.",
            "Permite usar servicios PostgreSQL externos.",
            "Evita depender únicamente del almacenamiento temporal del despliegue.",
        ),
    },
)


_DATE_FORMAT = "%Y-%m-%d"
_TRACKING_SECTION = "whats_new_acknowledgements"


def _activate_backup() -> None:
    if _TRACKING_SECTION not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, _TRACKING_SECTION)
        session_backup.SECTION_LABELS[_TRACKING_SECTION] = "Seguimiento de novedades"
        session_backup.SESSION_KEYS = (
            "general_settings",
            *session_backup.LIST_SECTIONS,
            *session_backup.DICT_SECTIONS,
        )


_activate_backup()


def _styles() -> None:
    st.markdown(
        """
        <style>
        .cm-news-hero{padding:1.55rem;border-radius:22px;background:linear-gradient(135deg,rgba(109,74,255,.16),rgba(34,166,161,.10));border:1px solid rgba(109,74,255,.16);margin-bottom:1rem}
        .cm-news-kicker{font-size:.72rem;font-weight:850;letter-spacing:.13em;color:#6d4aff}
        .cm-news-title{font-size:1.9rem;font-weight:850;color:#172033;margin:.3rem 0}
        .cm-news-copy{color:#64748b;max-width:800px}
        .cm-news-version{display:inline-block;margin-top:.8rem;padding:.35rem .65rem;border-radius:999px;background:white;color:#475569;font-size:.78rem;font-weight:700}
        .cm-news-badge{display:inline-block;padding:.22rem .52rem;border-radius:999px;background:rgba(109,74,255,.10);color:#5b3fd0;font-size:.72rem;font-weight:800;margin:.15rem .3rem .15rem 0}
        .cm-news-unread{display:inline-block;padding:.22rem .52rem;border-radius:999px;background:rgba(239,68,68,.10);color:#b91c1c;font-size:.72rem;font-weight:800}
        .cm-news-action{padding:.8rem .9rem;border-radius:14px;background:rgba(245,158,11,.09);border:1px solid rgba(245,158,11,.18);color:#92400e;margin:.65rem 0}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _current_user_id() -> str:
    user = auth.current_user()
    return str(user.user_id if user else "anonymous")


def _tracking_rows() -> list[dict]:
    return read_list(_TRACKING_SECTION)


def _read_ids(user_id: str) -> set[str]:
    return {
        str(row.get("news_id"))
        for row in _tracking_rows()
        if str(row.get("user_id")) == user_id and row.get("reviewed", True)
    }


def _mark_read(user_id: str, item_id: str) -> None:
    rows = _tracking_rows()
    updated = []
    found = False
    for row in rows:
        current = dict(row)
        if str(current.get("user_id")) == user_id and str(current.get("news_id")) == item_id:
            current.update({"reviewed": True, "reviewed_at_utc": now_iso()})
            found = True
        updated.append(current)
    if not found:
        updated.append({
            "user_id": user_id,
            "news_id": item_id,
            "reviewed": True,
            "reviewed_at_utc": now_iso(),
        })
    save_list(_TRACKING_SECTION, updated)


def _mark_all_read(user_id: str) -> None:
    for item in WHATS_NEW:
        _mark_read(user_id, item["id"])


def _date_label(value: str) -> str:
    parsed = datetime.strptime(value, _DATE_FORMAT)
    months = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"


def _matches(item: dict, query: str, category: str, status: str, impact: str, change_type: str, only_unread: bool, read: set[str]) -> bool:
    searchable = " ".join((item["title"], item["summary"], item["category"], item["audience"], item["action"], *item["details"])).casefold()
    return not (
        (query and query not in searchable)
        or (category != "Todas" and item["category"] != category)
        or (status != "Todos" and item["status"] != status)
        or (impact != "Todos" and item["impact"] != impact)
        or (change_type != "Todos" and item["change_type"] != change_type)
        or (only_unread and item["id"] in read)
    )


def _render_change(item: dict, key_prefix: str, user_id: str, read: set[str]) -> None:
    unread = item["id"] not in read
    with st.container(border=True):
        left, right = st.columns([5, 1.25])
        with left:
            badges = "".join(
                f'<span class="cm-news-badge">{label}</span>'
                for label in (item["version"], item["category"], item["change_type"], f'Impacto {item["impact"].lower()}', item["status"])
            )
            if unread:
                badges += '<span class="cm-news-unread">Sin revisar</span>'
            st.markdown(badges, unsafe_allow_html=True)
            st.markdown(f"### {item['title']}")
            st.write(item["summary"])
            st.caption(f"Para: {item['audience']} · Publicado: {_date_label(item['date'])}")
            if item["requires_action"]:
                st.markdown(f'<div class="cm-news-action"><strong>Acción recomendada:</strong> {item["action"]}</div>', unsafe_allow_html=True)
            with st.expander("Qué incluye"):
                for detail in item["details"]:
                    st.markdown(f"- {detail}")
        with right:
            if item.get("target") and st.button("Abrir módulo", key=f"{key_prefix}_open_{item['id']}", use_container_width=True, type="primary"):
                _mark_read(user_id, item["id"])
                app_shell.go_to(item["target"])
            if unread and st.button("Marcar revisada", key=f"{key_prefix}_read_{item['id']}", use_container_width=True):
                _mark_read(user_id, item["id"])
                st.rerun()


def _render_versions(read: set[str], user_id: str) -> None:
    versions = sorted({item["version"] for item in WHATS_NEW}, reverse=True)
    for version in versions:
        items = [item for item in WHATS_NEW if item["version"] == version]
        pending = sum(item["id"] not in read for item in items)
        action_required = sum(item["requires_action"] for item in items)
        with st.expander(
            f"Versión {version} · {len(items)} cambio(s) · {pending} sin revisar · {action_required} con acción",
            expanded=version == versions[0],
        ):
            for index, item in enumerate(sorted(items, key=lambda row: row["date"], reverse=True)):
                _render_change(item, f"version_{version}_{index}", user_id, read)


def render_whats_new() -> None:
    """Muestra cambios recientes, acciones requeridas y adopción por usuario."""
    _styles()
    user_id = _current_user_id()
    read = _read_ids(user_id)

    st.markdown(
        f"""
        <div class="cm-news-hero">
          <div class="cm-news-kicker">CENTRO DE ACTUALIZACIONES</div>
          <div class="cm-news-title">Qué cambió y qué debes hacer</div>
          <div class="cm-news-copy">Consulta versiones, revisa cambios importantes y completa las acciones necesarias para aprovechar el ERP.</div>
          <div class="cm-news-version">Versión instalada {APP_VERSION} · {PROJECT_STATUS}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    unread_count = sum(item["id"] not in read for item in WHATS_NEW)
    action_pending = sum(item["requires_action"] and item["id"] not in read for item in WHATS_NEW)
    high_pending = sum(item["impact"] == "Alta" and item["id"] not in read for item in WHATS_NEW)
    adoption_pct = (len(read.intersection({item["id"] for item in WHATS_NEW})) / len(WHATS_NEW) * 100) if WHATS_NEW else 100.0

    metrics = st.columns(4)
    metrics[0].metric("Cambios publicados", len(WHATS_NEW))
    metrics[1].metric("Sin revisar", unread_count)
    metrics[2].metric("Acciones pendientes", action_pending)
    metrics[3].metric("Adopción personal", f"{adoption_pct:.0f}%")
    st.progress(min(adoption_pct / 100, 1.0))

    action_left, action_right = st.columns([5, 1])
    action_left.caption(f"Tienes {high_pending} cambio(s) de impacto alto pendiente(s). El seguimiento queda asociado a tu usuario y se incluye en el respaldo general.")
    if unread_count and action_right.button("Marcar todo revisado", use_container_width=True):
        _mark_all_read(user_id)
        st.rerun()

    for_you, versions_tab, all_changes, adoption = st.tabs(("Para ti", "Versiones", "Todos los cambios", "Adopción"))

    with for_you:
        priority = [
            item for item in WHATS_NEW
            if item["id"] not in read and (item["requires_action"] or item["impact"] == "Alta")
        ]
        priority.sort(key=lambda item: (not item["requires_action"], item["date"]), reverse=False)
        if not priority:
            st.success("No tienes cambios prioritarios pendientes de revisar.")
        for index, item in enumerate(priority):
            _render_change(item, f"priority_{index}", user_id, read)

    with versions_tab:
        _render_versions(read, user_id)

    with all_changes:
        first = st.columns([1.4, 1, 1])
        query = first[0].text_input("Buscar", placeholder="Ej. inventario, compras, fiscal").strip().casefold()
        category = first[1].selectbox("Categoría", ("Todas", *sorted({item["category"] for item in WHATS_NEW})))
        status = first[2].selectbox("Estado", ("Todos", *sorted({item["status"] for item in WHATS_NEW})))
        second = st.columns([1, 1, 1])
        impact = second[0].selectbox("Impacto", ("Todos", "Alta", "Media", "Baja"))
        change_type = second[1].selectbox("Tipo de cambio", ("Todos", *sorted({item["change_type"] for item in WHATS_NEW})))
        only_unread = second[2].toggle("Solo sin revisar")

        visible = [item for item in WHATS_NEW if _matches(item, query, category, status, impact, change_type, only_unread, read)]
        visible.sort(key=lambda item: item["date"], reverse=True)
        st.caption(f"{len(visible)} resultado(s)")
        if not visible:
            st.info("No hay novedades que coincidan con los filtros seleccionados.")
        for index, item in enumerate(visible):
            _render_change(item, f"all_{index}", user_id, read)

    with adoption:
        st.markdown("### Adopción por área")
        for area in sorted({item["category"] for item in WHATS_NEW}):
            items = [item for item in WHATS_NEW if item["category"] == area]
            reviewed = sum(item["id"] in read for item in items)
            pct = reviewed / len(items) if items else 1.0
            columns = st.columns([3, 1])
            columns[0].markdown(f"**{area}**")
            columns[0].progress(pct)
            columns[1].metric("Revisadas", f"{reviewed}/{len(items)}")

        st.markdown("### Acciones recomendadas pendientes")
        pending_actions = [item for item in WHATS_NEW if item["requires_action"] and item["id"] not in read]
        if not pending_actions:
            st.success("No quedan acciones recomendadas pendientes.")
        for item in pending_actions:
            st.markdown(f"- **{item['title']}:** {item['action']}")

    st.divider()
    st.caption("Novedades registra únicamente la revisión de cambios; no modifica ventas, inventario, compras ni otros datos operativos.")


app_shell.FUNCTIONAL_MODULES["Novedades"] = render_whats_new
