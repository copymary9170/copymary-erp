"""Interfaz principal con navegación superior y módulos divididos en tarjetas."""

import streamlit as st

# Importar esta extensión registra todos los módulos funcionales y sus grupos.
from src import app_shell, app_shell_payments, auth
from src.components import apply_base_styles
from src.config import APP_NAME, APP_VERSION, PROJECT_STATUS
from src.modern_styles import apply_modern_styles


MODULE_DESCRIPTIONS = {
    "Inicio": "Resumen general y accesos principales.",
    "Centro de control": "Alertas, pendientes y decisiones del negocio.",
    "Auditoría de datos": "Revisión de cambios, integridad y trazabilidad.",
    "Metas del negocio": "Objetivos, avances y acciones prioritarias.",
    "Panel comercial": "Indicadores de ventas, clientes y pedidos.",
    "Panel financiero y cierres": "Resultados, caja y cierres financieros.",
    "Clientes": "Registro, consulta y seguimiento de clientes.",
    "Cotizaciones": "Preparación y seguimiento de presupuestos.",
    "Ventas y pedidos": "Gestión comercial desde el pedido hasta la entrega.",
    "Agenda de producción y entregas": "Planificación de trabajos, capacidad y fechas.",
    "Cuentas por cobrar": "Saldos pendientes y control de cobros.",
    "Comprobantes": "Documentos y soportes de las operaciones comerciales.",
    "Reportes comerciales": "Análisis de ventas, clientes y rendimiento.",
    "Proveedores": "Directorio, condiciones y seguimiento de proveedores.",
    "Compras": "Solicitudes, recepciones y control de abastecimiento.",
    "Cuentas por pagar": "Compromisos, vencimientos y pagos pendientes.",
    "Catálogo y producción": "Productos, servicios, recetas y procesos.",
    "Mantenimiento del catálogo": "Actualizaciones masivas y depuración del catálogo.",
    "Reversos de producción": "Corrección controlada de movimientos productivos.",
    "Inventario": "Existencias, disponibilidad y control de materiales.",
    "Movimientos de inventario": "Entradas, salidas, ajustes y trazabilidad.",
    "Alertas de inventario": "Faltantes, mínimos y necesidades de reposición.",
    "Costeo": "Costos de materiales, procesos y márgenes.",
    "Ajustar precios": "Redondeo y actualización de precios de venta.",
    "Exportar precios": "Generación de listados y archivos de precios.",
    "Caja": "Ingresos, egresos y movimientos diarios.",
    "Conciliación financiera": "Comparación y validación de movimientos.",
    "Reabrir cierre de caja": "Reapertura controlada de cierres realizados.",
    "Gastos y presupuesto": "Control de gastos, límites y planificación.",
    "Equipo y comisiones": "Asignación y cálculo de comisiones.",
    "Historial de comisiones": "Consulta de comisiones generadas y pagadas.",
    "Reversos de pagos": "Correcciones seguras de pagos registrados.",
    "Anulaciones y ajustes": "Rectificaciones con trazabilidad y auditoría.",
    "Activos": "Equipos, depreciación y control patrimonial.",
    "Respaldo general": "Copia y restauración de la información del ERP.",
    "Respaldar activos": "Respaldo específico de equipos y activos.",
    "Configuración General": "Parámetros generales del sistema y del negocio.",
}


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {display:none;}
        [data-testid="collapsedControl"] {display:none;}
        .block-container {padding-top:1.1rem; max-width:1600px;}
        .cm-topbar {display:flex;align-items:center;justify-content:space-between;gap:1rem;
            padding:.75rem 1rem;margin-bottom:.75rem;border:1px solid rgba(109,74,255,.14);
            border-radius:18px;background:rgba(255,255,255,.94);box-shadow:0 8px 24px rgba(31,41,55,.06)}
        .cm-topbar__brand {display:flex;align-items:center;gap:.75rem;}
        .cm-topbar__mark {display:grid;place-items:center;width:42px;height:42px;border-radius:13px;
            background:linear-gradient(135deg,#6D4AFF,#22A6A1);color:#fff;font-weight:900;}
        .cm-topbar__name {font-weight:850;font-size:1.08rem;color:#1f2937;}
        .cm-topbar__tag {font-size:.76rem;color:#7c8494;}
        .cm-module-heading {margin:.9rem 0 .25rem;font-size:1.05rem;font-weight:800;color:#1f2937;}
        .cm-module-caption {margin-bottom:.8rem;color:#64748b;font-size:.88rem;}
        div[data-testid="stRadio"] > div {gap:.35rem;flex-wrap:wrap;}
        div[data-testid="stRadio"] label {background:#fff;border:1px solid rgba(109,74,255,.16);
            border-radius:12px;padding:.45rem .72rem;box-shadow:0 3px 10px rgba(31,41,55,.035)}
        div[data-testid="stButton"] button {min-height:2.65rem;border-radius:12px;}
        @media(max-width:768px){.cm-topbar{align-items:flex-start;flex-direction:column}.block-container{padding:.7rem .8rem 2rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _effective_groups(user) -> tuple[dict[str, tuple[str, ...]], set[str] | None]:
    allowed_modules = auth.allowed_modules_for_role(user.role_id, user.role_name)
    if allowed_modules is None:
        return app_shell.NAVIGATION_GROUPS, None

    groups: dict[str, tuple[str, ...]] = {}
    for area, pages in app_shell.NAVIGATION_GROUPS.items():
        kept = tuple(page for page in pages if page == "Inicio" or page in allowed_modules)
        if kept:
            groups[area] = kept
    return groups or {"Inicio": ("Inicio",)}, allowed_modules


def _render_section_cards(area: str, pages: tuple[str, ...]) -> str:
    """Muestra las opciones del módulo como cuadros y devuelve la sección activa."""
    current = st.session_state.get("navigation_page")
    if current not in pages:
        current = pages[0]
        st.session_state["navigation_page"] = current

    if len(pages) == 1:
        return pages[0]

    st.markdown(f'<div class="cm-module-heading">Opciones de {area}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="cm-module-caption">Cada cuadro abre una sección independiente dentro de este módulo.</div>',
        unsafe_allow_html=True,
    )

    columns = st.columns(min(4, len(pages)))
    for index, page in enumerate(pages):
        with columns[index % len(columns)]:
            with st.container(border=True):
                st.markdown(f"**{page}**")
                st.caption(MODULE_DESCRIPTIONS.get(page, "Herramientas y operaciones de esta sección."))
                active = page == current
                if st.button(
                    "Abierto" if active else "Abrir",
                    key=f"topnav_page_{area}_{page}",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                    disabled=active,
                ):
                    st.session_state["navigation_page"] = page
                    st.rerun()
    return st.session_state["navigation_page"]


def run_app() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="CM",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_base_styles()
    apply_modern_styles()
    _apply_styles()
    app_shell._apply_pending_navigation()

    if not auth.require_login():
        return

    user = auth.current_user()
    effective_groups, allowed_modules = _effective_groups(user)

    st.markdown(
        '<div class="cm-topbar"><div class="cm-topbar__brand"><div class="cm-topbar__mark">CM</div>'
        '<div><div class="cm-topbar__name">CopyMary ERP</div><div class="cm-topbar__tag">Tu negocio, claro y organizado</div></div></div>'
        f'<div class="cm-topbar__tag">{user.display_name} · {user.role_name}</div></div>',
        unsafe_allow_html=True,
    )

    top_left, top_right = st.columns([7, 1])
    with top_right:
        if st.button("Cerrar sesión", use_container_width=True, key="top_logout_button"):
            auth.logout()
            st.rerun()

    st.session_state.setdefault("navigation_area", "Inicio")
    if st.session_state["navigation_area"] not in effective_groups:
        st.session_state["navigation_area"] = next(iter(effective_groups))

    with top_left:
        selected_area = st.radio(
            "Módulos principales",
            tuple(effective_groups.keys()),
            key="navigation_area",
            horizontal=True,
            label_visibility="collapsed",
        )

    available_pages = effective_groups[selected_area]
    selected_page = _render_section_cards(selected_area, available_pages)

    st.divider()
    if allowed_modules is not None and selected_page != "Inicio" and selected_page not in allowed_modules:
        st.error("No tienes permiso para ver esta sección. Pide acceso a un administrador.")
        return

    if selected_page == "Inicio":
        app_shell.render_home()
    elif selected_page in app_shell.FUNCTIONAL_MODULES:
        app_shell.FUNCTIONAL_MODULES[selected_page]()
    else:
        app_shell.render_descriptive_module(selected_page)

    st.caption(f"Versión {APP_VERSION} · {PROJECT_STATUS} · Guarda un respaldo antes de cerrar la sesión.")
