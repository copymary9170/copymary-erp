"""Shell ejecutivo de CopyMary Enterprise ERP."""

import streamlit as st

from src import app_shell, app_shell_payments, auth
from src.components import apply_base_styles
from src.config import APP_NAME, APP_VERSION, PROJECT_STATUS
from src.enterprise_ui_theme import apply_enterprise_theme
from src.modern_styles import apply_modern_styles


SPECIALTY_AREAS = {
    "Inicio": ("⌂", "Vista ejecutiva", "Resumen general, alertas y accesos de uso diario.", ("Inicio", "Novedades", "Centro de control", "Metas del negocio", "Panel comercial", "Auditoría de datos", "Fundación técnica")),
    "Comercial y CRM": ("◎", "Relación con clientes", "Clientes, cotizaciones, ventas, pedidos y cobros.", ("Clientes", "Cotizaciones", "Ventas y pedidos", "Venta rápida de mostrador", "Agenda de producción y entregas", "Cuentas por cobrar", "Comprobantes", "Reportes comerciales")),
    "Compras y abastecimiento": ("◇", "Cadena de suministro", "Proveedores, compras, recepción y cuentas por pagar.", ("Proveedores", "Compras", "Cuentas por pagar")),
    "Producción": ("◫", "Operación productiva", "Catálogo productivo, órdenes, capacidad y reversos.", ("Catálogo y producción", "Órdenes de producción", "Mantenimiento del catálogo", "Reversos de producción")),
    "Inventario y almacén": ("▦", "Control de existencias", "Existencias, movimientos, ajustes y alertas de stock.", ("Inventario", "Movimientos de inventario", "Ajustes de inventario", "Alertas de inventario")),
    "Costos y precios": ("◈", "Rentabilidad", "Costeo, recetas, márgenes, tasas y precios de venta.", ("Costeo", "Costeo por procesos", "BOM multinivel", "Tasas de cambio", "Ajustar precios", "Exportar precios")),
    "Finanzas y tesorería": ("◉", "Control financiero", "Caja, conciliación, gastos, pagos, ajustes y cierres.", ("Panel financiero y cierres", "Caja", "Conciliación financiera", "Reabrir cierre de caja", "Gastos y presupuesto", "Reversos de pagos", "Anulaciones y ajustes")),
    "Contabilidad y análisis": ("◌", "Análisis gerencial", "Resultados financieros y proyecciones de efectivo.", ("Estado de Resultados", "Flujo de caja proyectado")),
    "Talento humano": ("◍", "Gestión de personas", "Empleados, nómina, equipo y comisiones.", ("RRHH y nómina", "Equipo y comisiones", "Historial de comisiones")),
    "Activos y mantenimiento": ("△", "Infraestructura", "Equipos, depreciación y mantenimiento preventivo.", ("Activos", "Mantenimiento preventivo")),
    "Administración y seguridad": ("⬡", "Gobierno del sistema", "Usuarios, roles, permisos y configuración general.", ("Usuarios y roles", "Configuración General")),
    "Respaldos": ("↻", "Continuidad operativa", "Copias de seguridad y restauración de información.", ("Respaldo general", "Respaldar activos")),
}

DESCRIPTIONS = {
    "Inicio": "Panel general del negocio y accesos prioritarios.", "Novedades": "Cambios recientes y nuevas capacidades del ERP.",
    "Centro de control": "Alertas, pendientes y decisiones del día.", "Metas del negocio": "Objetivos, avances y acciones estratégicas.",
    "Panel comercial": "Indicadores de ventas, clientes y pedidos.", "Auditoría de datos": "Integridad, cambios y trazabilidad de la información.",
    "Fundación técnica": "Estado de los componentes esenciales del sistema.", "Clientes": "Registro y seguimiento de clientes.",
    "Cotizaciones": "Presupuestos y seguimiento comercial.", "Ventas y pedidos": "Pedidos desde el registro hasta la entrega.",
    "Venta rápida de mostrador": "Venta directa y cobro inmediato.", "Agenda de producción y entregas": "Planificación de fechas, trabajos y capacidad.",
    "Cuentas por cobrar": "Cobros pendientes, saldos y vencimientos.", "Comprobantes": "Soportes de operaciones comerciales.",
    "Reportes comerciales": "Rendimiento de ventas y clientes.", "Proveedores": "Directorio y evaluación de proveedores.",
    "Compras": "Abastecimiento, recepción y control de compras.", "Cuentas por pagar": "Vencimientos y obligaciones pendientes.",
    "Catálogo y producción": "Productos, servicios, recetas y procesos.", "Órdenes de producción": "Ejecución y seguimiento de trabajos.",
    "Mantenimiento del catálogo": "Actualización y depuración del catálogo.", "Reversos de producción": "Corrección controlada de operaciones productivas.",
    "Inventario": "Existencias y disponibilidad de materiales.", "Movimientos de inventario": "Entradas, salidas y trazabilidad.",
    "Ajustes de inventario": "Correcciones autorizadas de existencias.", "Alertas de inventario": "Mínimos y necesidades de reposición.",
    "Costeo": "Costos, consumos y márgenes.", "Costeo por procesos": "Costos detallados por etapa.", "BOM multinivel": "Materiales y componentes anidados.",
    "Tasas de cambio": "Tasas monetarias aplicables.", "Ajustar precios": "Actualización controlada de precios.", "Exportar precios": "Listados y archivos de precios.",
    "Panel financiero y cierres": "Indicadores y cierres financieros.", "Caja": "Ingresos, egresos y movimientos diarios.",
    "Conciliación financiera": "Validación de movimientos financieros.", "Reabrir cierre de caja": "Reapertura autorizada de cierres.",
    "Gastos y presupuesto": "Gastos, límites y planificación.", "Reversos de pagos": "Correcciones seguras de pagos registrados.",
    "Anulaciones y ajustes": "Rectificaciones con trazabilidad.", "Estado de Resultados": "Ingresos, costos, gastos y rentabilidad.",
    "Flujo de caja proyectado": "Proyección de efectivo a futuro.", "RRHH y nómina": "Empleados, períodos y recibos de pago.",
    "Equipo y comisiones": "Asignación y cálculo de comisiones.", "Historial de comisiones": "Consulta histórica de comisiones.",
    "Activos": "Equipos, depreciación y patrimonio.", "Mantenimiento preventivo": "Calendario y bitácora de máquinas.",
    "Usuarios y roles": "Accesos, roles y permisos.", "Configuración General": "Parámetros del sistema y del negocio.",
    "Respaldo general": "Copia y restauración integral del ERP.", "Respaldar activos": "Respaldo específico de activos.",
}


def _effective_areas(user):
    allowed = auth.allowed_modules_for_role(user.role_id, user.role_name)
    registered = set(app_shell.FUNCTIONAL_MODULES)
    for pages in app_shell.NAVIGATION_GROUPS.values():
        registered.update(pages)
    registered.add("Inicio")
    areas = {}
    for area, (icon, eyebrow, description, pages) in SPECIALTY_AREAS.items():
        visible = tuple(page for page in pages if page in registered and (allowed is None or page == "Inicio" or page in allowed))
        if visible:
            areas[area] = (icon, eyebrow, description, visible)
    return areas or {"Inicio": SPECIALTY_AREAS["Inicio"]}, allowed


def _render_module_cards(area: str, pages: tuple[str, ...]) -> str:
    current = st.session_state.get("navigation_page")
    if current not in pages:
        current = pages[0]
        st.session_state["navigation_page"] = current
    if len(pages) == 1:
        return pages[0]

    st.markdown(f'<div class="cm-section-head"><div class="cm-section-title">Herramientas del área</div><div class="cm-section-meta">{len(pages)} módulos disponibles</div></div>', unsafe_allow_html=True)
    columns = st.columns(3)
    for index, page in enumerate(pages):
        active = page == current
        with columns[index % 3]:
            with st.container(border=True):
                badge = "cm-card-badge cm-card-active" if active else "cm-card-badge"
                st.markdown(
                    f'<div class="cm-card-top"><span class="{badge}">{"En uso" if active else "Módulo"}</span><span class="cm-card-arrow">↗</span></div>'
                    f'<div class="cm-card-title">{page}</div><div class="cm-card-copy">{DESCRIPTIONS.get(page, "Herramientas y operaciones de esta especialidad.")}</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Módulo abierto" if active else "Abrir módulo", key=f"specialty_{area}_{page}", use_container_width=True, type="primary" if active else "secondary", disabled=active):
                    st.session_state["navigation_page"] = page
                    st.rerun()
    return st.session_state["navigation_page"]


def _render_current_page(selected_page: str, allowed) -> None:
    if allowed is not None and selected_page != "Inicio" and selected_page not in allowed:
        st.error("No tienes permiso para ver esta sección.")
        return
    st.markdown('<div class="cm-content-frame">', unsafe_allow_html=True)
    if selected_page == "Inicio":
        app_shell.render_home()
    elif selected_page in app_shell.FUNCTIONAL_MODULES:
        app_shell.FUNCTIONAL_MODULES[selected_page]()
    else:
        app_shell.render_descriptive_module(selected_page)
    st.markdown('</div>', unsafe_allow_html=True)


def run_app() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="CM", layout="wide", initial_sidebar_state="collapsed")
    apply_base_styles()
    apply_modern_styles()
    apply_enterprise_theme()
    app_shell._apply_pending_navigation()
    if not auth.require_login():
        return

    user = auth.current_user()
    areas, allowed = _effective_areas(user)
    st.session_state.setdefault("navigation_area", "Inicio")
    if st.session_state["navigation_area"] not in areas:
        st.session_state["navigation_area"] = next(iter(areas))

    st.markdown(
        f'<div class="cm-shell"><div class="cm-topline"><div class="cm-brand"><div class="cm-logo">CM</div><div><div class="cm-brand-title">CopyMary Enterprise</div><div class="cm-brand-subtitle">ERP integral para impresión, papelería y servicios</div></div></div><div class="cm-account"><span class="cm-account-dot"></span><div><div class="cm-account-name">{user.display_name}</div><div class="cm-account-role">{user.role_name}</div></div></div></div><div class="cm-nav-label">Áreas de especialidad</div></div>',
        unsafe_allow_html=True,
    )

    nav, action = st.columns([10, 1])
    with nav:
        selected_area = st.radio("Áreas", tuple(areas), key="navigation_area", horizontal=True, label_visibility="collapsed")
    with action:
        if st.button("Salir", key="top_logout_button", use_container_width=True):
            auth.logout()
            st.rerun()

    icon, eyebrow, description, pages = areas[selected_area]
    st.markdown(f'<div class="cm-workspace"><div><div class="cm-eyebrow">{eyebrow}</div><div class="cm-workspace-title">{selected_area}</div><div class="cm-workspace-copy">{description}</div></div><div class="cm-workspace-icon">{icon}</div></div>', unsafe_allow_html=True)
    selected_page = _render_module_cards(selected_area, tuple(pages))
    _render_current_page(selected_page, allowed)
    st.markdown(f'<div class="cm-footer">Versión {APP_VERSION} · {PROJECT_STATUS} · Mantén respaldos periódicos de la información.</div>', unsafe_allow_html=True)
