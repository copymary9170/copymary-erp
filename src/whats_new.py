"""Centro de novedades y adopción de CopyMary ERP."""
from __future__ import annotations

import streamlit as st

from src import app_shell
from src.config import APP_VERSION, PROJECT_STATUS


WHATS_NEW = (
    {
        "title": "Inicio y navegación reparados",
        "summary": "Se corrigieron accesos inválidos, paneles sustituidos y páginas duplicadas de Streamlit.",
        "category": "Experiencia",
        "status": "Disponible",
        "impact": "Alta",
        "date": "26 jul 2026",
        "target": "Inicio",
        "details": (
            "Panel comercial y panel financiero vuelven a ser independientes.",
            "El tablero ejecutivo conserva una entrada propia.",
            "Catálogo y recepción dejaron de mostrarse como páginas duplicadas.",
        ),
    },
    {
        "title": "Catálogo integrado en Inventario",
        "summary": "La ficha técnica de artículos se incorporó al flujo de Inventario para evitar módulos aislados.",
        "category": "Inventario",
        "status": "Disponible",
        "impact": "Alta",
        "date": "26 jul 2026",
        "target": "Inventario",
        "details": (
            "Medidas reales de los cuatro lados y área utilizable.",
            "Gramaje, peso, volumen y calidad del corte.",
            "Migración segura de artículos existentes.",
        ),
    },
    {
        "title": "Recepción integrada en Compras",
        "summary": "La recepción parcial de mercancía ahora forma parte del ciclo completo de abastecimiento.",
        "category": "Compras",
        "status": "Disponible",
        "impact": "Alta",
        "date": "26 jul 2026",
        "target": "Compras",
        "details": (
            "Recepciones parciales y cantidades pendientes.",
            "Condición, responsable y observaciones de recepción.",
            "Seguimiento conjunto de pedido, recepción y pago.",
        ),
    },
    {
        "title": "Tablero ejecutivo real",
        "summary": "Indicadores de ventas, margen, clientes, entregas, capacidad, mermas y aprobaciones.",
        "category": "Analítica",
        "status": "Disponible",
        "impact": "Media",
        "date": "26 jul 2026",
        "target": "Tablero ejecutivo",
        "details": (
            "Rentabilidad por producto o servicio.",
            "Comparación contra el período anterior.",
            "Trazabilidad de aprobaciones y cambios.",
        ),
    },
    {
        "title": "Control laboral venezolano",
        "summary": "Expedientes, asistencia, vacaciones, prestaciones y recibos de pago dentro de RRHH.",
        "category": "Talento humano",
        "status": "Disponible",
        "impact": "Alta",
        "date": "26 jul 2026",
        "target": "RRHH y nómina",
        "details": (
            "Gestión de asistencia y ausencias.",
            "Cálculos referenciales de vacaciones y prestaciones.",
            "Recibos de pago exportables.",
        ),
    },
    {
        "title": "Cumplimiento fiscal y documental",
        "summary": "Validaciones fiscales, contratos y retención inalterable de documentos legales.",
        "category": "Legal",
        "status": "Disponible",
        "impact": "Alta",
        "date": "26 jul 2026",
        "target": "Comprobantes",
        "details": (
            "Validación de datos fiscales obligatorios.",
            "Contratos y términos editables.",
            "Cadena de integridad para detectar alteraciones.",
        ),
    },
    {
        "title": "Tasas, IVA, IGTF y comisiones conectadas",
        "summary": "Las ventas usan la configuración monetaria vigente y conservan el neto realmente recibido.",
        "category": "Finanzas",
        "status": "Disponible",
        "impact": "Alta",
        "date": "24 jul 2026",
        "target": "Configuración General",
        "details": (
            "IVA manual por venta.",
            "Comisiones e IGTF aplicados sobre el monto procesado.",
            "Historial de tasas y aviso cuando están desactualizadas.",
        ),
    },
    {
        "title": "Persistencia con PostgreSQL externo",
        "summary": "El ERP puede conservar datos fuera del disco efímero de Streamlit Cloud.",
        "category": "Infraestructura",
        "status": "Requiere configuración",
        "impact": "Alta",
        "date": "24 jul 2026",
        "target": None,
        "details": (
            "Compatible con COPYMARY_DATABASE_URL y Secrets de Streamlit.",
            "Permite usar servicios PostgreSQL externos.",
            "Evita depender únicamente del almacenamiento temporal del despliegue.",
        ),
    },
)


def _styles() -> None:
    st.markdown(
        """
        <style>
        .cm-news-hero{padding:1.4rem 1.5rem;border-radius:22px;background:linear-gradient(135deg,rgba(109,74,255,.14),rgba(34,166,161,.10));border:1px solid rgba(109,74,255,.16);margin-bottom:1rem}
        .cm-news-kicker{font-size:.72rem;font-weight:850;letter-spacing:.13em;color:#6d4aff}
        .cm-news-title{font-size:1.8rem;font-weight:850;color:#172033;margin:.3rem 0}
        .cm-news-copy{color:#64748b;max-width:760px}
        .cm-news-version{display:inline-block;margin-top:.8rem;padding:.35rem .65rem;border-radius:999px;background:white;color:#475569;font-size:.78rem;font-weight:700}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_whats_new() -> None:
    """Muestra cambios recientes con filtros, impacto y accesos directos."""
    _styles()
    st.markdown(
        f"""
        <div class="cm-news-hero">
          <div class="cm-news-kicker">CENTRO DE NOVEDADES</div>
          <div class="cm-news-title">Qué cambió en CopyMary ERP</div>
          <div class="cm-news-copy">Revisa las mejoras disponibles, su impacto y dónde encontrarlas dentro del sistema.</div>
          <div class="cm-news-version">Versión {APP_VERSION} · {PROJECT_STATUS}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    available = sum(item["status"] == "Disponible" for item in WHATS_NEW)
    high_impact = sum(item["impact"] == "Alta" for item in WHATS_NEW)
    categories = len({item["category"] for item in WHATS_NEW})
    metrics = st.columns(4)
    metrics[0].metric("Mejoras publicadas", len(WHATS_NEW))
    metrics[1].metric("Disponibles ahora", available)
    metrics[2].metric("Impacto alto", high_impact)
    metrics[3].metric("Áreas mejoradas", categories)

    st.markdown("### Explorar cambios")
    filters = st.columns([1.35, 1, 1, 1])
    query = filters[0].text_input("Buscar", placeholder="Ej. inventario, compras, fiscal").strip().casefold()
    category = filters[1].selectbox("Categoría", ("Todas", *sorted({item["category"] for item in WHATS_NEW})))
    status = filters[2].selectbox("Estado", ("Todos", *sorted({item["status"] for item in WHATS_NEW})))
    impact = filters[3].selectbox("Impacto", ("Todos", "Alta", "Media", "Baja"))

    visible = []
    for item in WHATS_NEW:
        searchable = " ".join((item["title"], item["summary"], item["category"], *item["details"])).casefold()
        if query and query not in searchable:
            continue
        if category != "Todas" and item["category"] != category:
            continue
        if status != "Todos" and item["status"] != status:
            continue
        if impact != "Todos" and item["impact"] != impact:
            continue
        visible.append(item)

    if not visible:
        st.info("No hay novedades que coincidan con los filtros seleccionados.")
        return

    current_date = None
    for index, item in enumerate(visible):
        if item["date"] != current_date:
            current_date = item["date"]
            st.markdown(f"#### {current_date}")
        with st.container(border=True):
            left, right = st.columns([5, 1.2])
            with left:
                st.caption(f"{item['category']} · {item['status']} · Impacto {item['impact'].lower()}")
                st.markdown(f"### {item['title']}")
                st.write(item["summary"])
                with st.expander("Ver detalles"):
                    for detail in item["details"]:
                        st.markdown(f"- {detail}")
            with right:
                if item.get("target"):
                    if st.button("Abrir módulo", key=f"news_open_{index}_{item['target']}", use_container_width=True, type="primary"):
                        app_shell.go_to(item["target"])

    st.divider()
    st.caption("Las novedades son una guía de cambios funcionales publicados. Esta pantalla no modifica datos operativos.")


app_shell.FUNCTIONAL_MODULES["Novedades"] = render_whats_new
