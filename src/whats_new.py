"""Centro de novedades, adopción y seguimiento de CopyMary ERP."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from src import app_shell
from src.config import APP_VERSION, PROJECT_STATUS


WHATS_NEW = (
    {
        "id": "inicio-navegacion-20260726",
        "title": "Inicio y navegación reparados",
        "summary": "Se corrigieron accesos inválidos, paneles sustituidos y páginas duplicadas de Streamlit.",
        "category": "Experiencia",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "Inicio",
        "audience": "Todo el equipo",
        "details": (
            "Panel comercial y panel financiero vuelven a ser independientes.",
            "El tablero ejecutivo conserva una entrada propia.",
            "Catálogo y recepción dejaron de mostrarse como páginas duplicadas.",
        ),
    },
    {
        "id": "catalogo-inventario-20260726",
        "title": "Catálogo integrado en Inventario",
        "summary": "La ficha técnica de artículos se incorporó al flujo de Inventario para evitar módulos aislados.",
        "category": "Inventario",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "Inventario",
        "audience": "Inventario y producción",
        "details": (
            "Medidas reales de los cuatro lados y área utilizable.",
            "Gramaje, peso, volumen y calidad del corte.",
            "Migración segura de artículos existentes.",
        ),
    },
    {
        "id": "recepcion-compras-20260726",
        "title": "Recepción integrada en Compras",
        "summary": "La recepción parcial de mercancía ahora forma parte del ciclo completo de abastecimiento.",
        "category": "Compras",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "Compras",
        "audience": "Compras y almacén",
        "details": (
            "Recepciones parciales y cantidades pendientes.",
            "Condición, responsable y observaciones de recepción.",
            "Seguimiento conjunto de pedido, recepción y pago.",
        ),
    },
    {
        "id": "tablero-ejecutivo-20260726",
        "title": "Tablero ejecutivo real",
        "summary": "Indicadores de ventas, margen, clientes, entregas, capacidad, mermas y aprobaciones.",
        "category": "Analítica",
        "status": "Disponible",
        "impact": "Media",
        "date": "2026-07-26",
        "target": "Tablero ejecutivo",
        "audience": "Dirección y administración",
        "details": (
            "Rentabilidad por producto o servicio.",
            "Comparación contra el período anterior.",
            "Trazabilidad de aprobaciones y cambios.",
        ),
    },
    {
        "id": "rrhh-laboral-20260726",
        "title": "Control laboral venezolano",
        "summary": "Expedientes, asistencia, vacaciones, prestaciones y recibos de pago dentro de RRHH.",
        "category": "Talento humano",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "RRHH y nómina",
        "audience": "Administración y RRHH",
        "details": (
            "Gestión de asistencia y ausencias.",
            "Cálculos referenciales de vacaciones y prestaciones.",
            "Recibos de pago exportables.",
        ),
    },
    {
        "id": "cumplimiento-legal-20260726",
        "title": "Cumplimiento fiscal y documental",
        "summary": "Validaciones fiscales, contratos y retención inalterable de documentos legales.",
        "category": "Legal",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-26",
        "target": "Comprobantes",
        "audience": "Administración y contabilidad",
        "details": (
            "Validación de datos fiscales obligatorios.",
            "Contratos y términos editables.",
            "Cadena de integridad para detectar alteraciones.",
        ),
    },
    {
        "id": "tasas-comisiones-20260724",
        "title": "Tasas, IVA, IGTF y comisiones conectadas",
        "summary": "Las ventas usan la configuración monetaria vigente y conservan el neto realmente recibido.",
        "category": "Finanzas",
        "status": "Disponible",
        "impact": "Alta",
        "date": "2026-07-24",
        "target": "Configuración General",
        "audience": "Ventas y administración",
        "details": (
            "IVA manual por venta.",
            "Comisiones e IGTF aplicados sobre el monto procesado.",
            "Historial de tasas y aviso cuando están desactualizadas.",
        ),
    },
    {
        "id": "postgresql-externo-20260724",
        "title": "Persistencia con PostgreSQL externo",
        "summary": "El ERP puede conservar datos fuera del disco efímero de Streamlit Cloud.",
        "category": "Infraestructura",
        "status": "Requiere configuración",
        "impact": "Alta",
        "date": "2026-07-24",
        "target": None,
        "audience": "Administración técnica",
        "details": (
            "Compatible con COPYMARY_DATABASE_URL y Secrets de Streamlit.",
            "Permite usar servicios PostgreSQL externos.",
            "Evita depender únicamente del almacenamiento temporal del despliegue.",
        ),
    },
)


_DATE_FORMAT = "%Y-%m-%d"
_READ_KEY = "whats_new_read_ids"


def _styles() -> None:
    st.markdown(
        """
        <style>
        .cm-news-hero{padding:1.5rem;border-radius:22px;background:linear-gradient(135deg,rgba(109,74,255,.15),rgba(34,166,161,.10));border:1px solid rgba(109,74,255,.16);margin-bottom:1rem}
        .cm-news-kicker{font-size:.72rem;font-weight:850;letter-spacing:.13em;color:#6d4aff}
        .cm-news-title{font-size:1.85rem;font-weight:850;color:#172033;margin:.3rem 0}
        .cm-news-copy{color:#64748b;max-width:780px}
        .cm-news-version{display:inline-block;margin-top:.8rem;padding:.35rem .65rem;border-radius:999px;background:white;color:#475569;font-size:.78rem;font-weight:700}
        .cm-news-badge{display:inline-block;padding:.2rem .5rem;border-radius:999px;background:rgba(109,74,255,.10);color:#5b3fd0;font-size:.72rem;font-weight:800;margin-right:.3rem}
        .cm-news-unread{display:inline-block;padding:.2rem .5rem;border-radius:999px;background:rgba(239,68,68,.10);color:#b91c1c;font-size:.72rem;font-weight:800}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _read_ids() -> set[str]:
    raw = st.session_state.setdefault(_READ_KEY, [])
    return {str(item) for item in raw}


def _mark_read(item_id: str) -> None:
    read = _read_ids()
    read.add(item_id)
    st.session_state[_READ_KEY] = sorted(read)


def _mark_all_read() -> None:
    st.session_state[_READ_KEY] = sorted(item["id"] for item in WHATS_NEW)


def _date_label(value: str) -> str:
    parsed = datetime.strptime(value, _DATE_FORMAT)
    months = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"


def _matches(item: dict, query: str, category: str, status: str, impact: str, only_unread: bool, read: set[str]) -> bool:
    searchable = " ".join((item["title"], item["summary"], item["category"], item["audience"], *item["details"])).casefold()
    return not (
        (query and query not in searchable)
        or (category != "Todas" and item["category"] != category)
        or (status != "Todos" and item["status"] != status)
        or (impact != "Todos" and item["impact"] != impact)
        or (only_unread and item["id"] in read)
    )


def _render_change(item: dict, index: int, read: set[str]) -> None:
    unread = item["id"] not in read
    with st.container(border=True):
        left, right = st.columns([5, 1.25])
        with left:
            badges = (
                f'<span class="cm-news-badge">{item["category"]}</span>'
                f'<span class="cm-news-badge">Impacto {item["impact"].lower()}</span>'
                f'<span class="cm-news-badge">{item["status"]}</span>'
            )
            if unread:
                badges += '<span class="cm-news-unread">Sin revisar</span>'
            st.markdown(badges, unsafe_allow_html=True)
            st.markdown(f"### {item['title']}")
            st.write(item["summary"])
            st.caption(f"Para: {item['audience']}")
            with st.expander("Qué incluye y cómo aprovecharlo"):
                for detail in item["details"]:
                    st.markdown(f"- {detail}")
        with right:
            if item.get("target") and st.button("Abrir módulo", key=f"news_open_{index}_{item['id']}", use_container_width=True, type="primary"):
                _mark_read(item["id"])
                app_shell.go_to(item["target"])
            if unread and st.button("Marcar revisada", key=f"news_read_{index}_{item['id']}", use_container_width=True):
                _mark_read(item["id"])
                st.rerun()


def render_whats_new() -> None:
    """Muestra cambios recientes con filtros, seguimiento y accesos directos."""
    _styles()
    st.markdown(
        f"""
        <div class="cm-news-hero">
          <div class="cm-news-kicker">CENTRO DE NOVEDADES</div>
          <div class="cm-news-title">Qué cambió en CopyMary ERP</div>
          <div class="cm-news-copy">Descubre mejoras, identifica cuáles requieren atención y entra directamente al módulo relacionado.</div>
          <div class="cm-news-version">Versión {APP_VERSION} · {PROJECT_STATUS}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    read = _read_ids()
    available = sum(item["status"] == "Disponible" for item in WHATS_NEW)
    unread_count = sum(item["id"] not in read for item in WHATS_NEW)
    high_impact = sum(item["impact"] == "Alta" for item in WHATS_NEW)
    adoption_pct = (len(read) / len(WHATS_NEW) * 100) if WHATS_NEW else 100.0

    metrics = st.columns(4)
    metrics[0].metric("Mejoras publicadas", len(WHATS_NEW))
    metrics[1].metric("Disponibles ahora", available)
    metrics[2].metric("Sin revisar", unread_count)
    metrics[3].metric("Adopción", f"{adoption_pct:.0f}%")
    st.progress(min(adoption_pct / 100, 1.0))

    action_left, action_right = st.columns([5, 1])
    action_left.caption(f"Hay {high_impact} cambios de impacto alto. Revisarlos ayuda a evitar que funciones importantes queden sin usar.")
    if unread_count and action_right.button("Marcar todo revisado", use_container_width=True):
        _mark_all_read()
        st.rerun()

    featured, all_changes, by_area = st.tabs(("Prioridad", "Todos los cambios", "Por área"))

    with featured:
        priority = [item for item in WHATS_NEW if item["impact"] == "Alta" and item["id"] not in read]
        if not priority:
            st.success("No quedan novedades prioritarias pendientes de revisar.")
        for index, item in enumerate(priority):
            _render_change(item, index, read)

    with all_changes:
        filters = st.columns([1.35, 1, 1, 1])
        query = filters[0].text_input("Buscar", placeholder="Ej. inventario, compras, fiscal").strip().casefold()
        category = filters[1].selectbox("Categoría", ("Todas", *sorted({item["category"] for item in WHATS_NEW})))
        status = filters[2].selectbox("Estado", ("Todos", *sorted({item["status"] for item in WHATS_NEW})))
        impact = filters[3].selectbox("Impacto", ("Todos", "Alta", "Media", "Baja"))
        only_unread = st.toggle("Mostrar solo novedades sin revisar")

        visible = [item for item in WHATS_NEW if _matches(item, query, category, status, impact, only_unread, read)]
        visible.sort(key=lambda item: item["date"], reverse=True)
        st.caption(f"{len(visible)} resultado(s)")
        if not visible:
            st.info("No hay novedades que coincidan con los filtros seleccionados.")
        current_date = None
        for index, item in enumerate(visible):
            if item["date"] != current_date:
                current_date = item["date"]
                st.markdown(f"#### {_date_label(current_date)}")
            _render_change(item, index + 100, read)

    with by_area:
        areas = sorted({item["category"] for item in WHATS_NEW})
        for area in areas:
            items = [item for item in WHATS_NEW if item["category"] == area]
            unread_area = sum(item["id"] not in read for item in items)
            with st.expander(f"{area} · {len(items)} cambio(s) · {unread_area} sin revisar", expanded=unread_area > 0):
                for index, item in enumerate(items):
                    _render_change(item, index + 200, read)

    st.divider()
    st.caption("El seguimiento de lectura se conserva durante la sesión actual. Novedades no modifica datos operativos.")


app_shell.FUNCTIONAL_MODULES["Novedades"] = render_whats_new
