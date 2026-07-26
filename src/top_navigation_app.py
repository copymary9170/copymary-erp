"""Shell ejecutivo de CopyMary Enterprise ERP."""

import streamlit as st

from src import app_shell_payments, auth
from src.components import apply_base_styles
from src.config import APP_NAME, APP_VERSION, PROJECT_STATUS
from src.enterprise_ui_theme import apply_enterprise_theme
from src.modern_styles import apply_modern_styles


SPECIALTY_AREAS = {
    "Inicio": ("⌂", "Vista ejecutiva", "Resumen general, alertas y accesos de uso diario.", ("Inicio", "Novedades", "Centro de control", "Metas del negocio", "Panel comercial", "Auditoría de datos", "Fundación técnica")),
    "Comercial y CRM": ("◎", "Relación con clientes", "Clientes, cotizaciones, ventas, pedidos y cobros.", ("Clientes", "Cotizaciones", "Ventas y pedidos", "Venta rápida de mostrador", "Agenda de producción y entregas", "Cuentas por cobrar", "Comprobantes", "Reportes comerciales")),
    "Compras y abastecimiento": ("◇", "Cadena de suministro", "Proveedores, órdenes de compra, recepción y cuentas por pagar.", ("Proveedores", "Compras", "Recepción de mercancía", "Cuentas por pagar")),
    "Producción": ("◫", "Operación productiva", "Catálogo productivo, órdenes, capacidad y reversos.", ("Catálogo y producción", "Órdenes de producción", "Mantenimiento del catálogo", "Reversos de producción")),
    "Inventario y almacén": ("▦", "Control de artículos y existencias", "Catálogo maestro, existencias, movimientos, ajustes y alertas de stock.", ("Catálogo de artículos", "Inventario", "Movimientos de inventario", "Ajustes de inventario", "Alertas de inventario")),
    "Costos y precios": ("◈", "Rentabilidad", "Costeo, recetas, márgenes, tasas y precios de venta.", ("Costeo", "Costeo por procesos", "BOM multinivel", "Tasas de cambio", "Ajustar precios", "Exportar precios")),
    "Finanzas y tesorería": ("◉", "Control financiero", "Caja, conciliación, gastos, pagos, ajustes y cierres.", ("Panel financiero y cierres", "Caja", "Conciliación financiera", "Reabrir cierre de caja", "Gastos y presupuesto", "Reversos de pagos", "Anulaciones y ajustes")),
    "Contabilidad y análisis": ("◌", "Análisis gerencial", "Resultados financieros y proyecciones de efectivo.", ("Estado de Resultados", "Flujo de caja proyectado")),
    "Talento humano": ("◍", "Gestión de personas", "Empleados, nómina, equipo y comisiones.", ("RRHH y nómina", "Equipo y comisiones", "Historial de comisiones")),
    "Activos y mantenimiento": ("△", "Infraestructura", "Equipos, depreciación y mantenimiento preventivo.", ("Activos", "Mantenimiento preventivo")),
    "Administración y seguridad": ("⬡", "Gobierno del sistema", "Usuarios, roles, permisos y configuración general.", ("Usuarios y roles", "Configuración General")),
    "Respaldos": ("↻", "Continuidad operativa", "Copias de seguridad y restauración de información.", ("Respaldo general", "Respaldar activos")),
}

DESCRIPTIONS = {
    "Inicio": "Panel general del negocio y accesos prioritarios.", "Novedades": "Cambios recientes del ERP.",
    "Centro de control": "Alertas y pendientes del día.", "Metas del negocio": "Objetivos y avances.",
    "Panel comercial": "Indicadores de ventas y clientes.", "Auditoría de datos": "Integridad y trazabilidad.",
    "Fundación técnica": "Estado técnico del sistema.", "Clientes": "Registro y seguimiento de clientes.",
    "Cotizaciones": "Presupuestos comerciales.", "Ventas y pedidos": "Pedidos hasta la entrega.",
    "Venta rápida de mostrador": "Venta directa y cobro inmediato.", "Agenda de producción y entregas": "Fechas y capacidad.",
    "Cuentas por cobrar": "Saldos y vencimientos.", "Comprobantes": "Soportes comerciales.",
    "Reportes comerciales": "Rendimiento de ventas.", "Proveedores": "Directorio de proveedores.",
    "Compras": "Órdenes y condiciones de adquisición sin alterar existencias.",
    "Recepción de mercancía": "Confirma lo recibido y actualiza inventario y costo promedio.",
    "Cuentas por pagar": "Obligaciones pendientes.",
    "Catálogo de artículos": "Definición maestra de materiales, productos, unidades y características.",
    "Catálogo y producción": "Productos, recetas y procesos.", "Órdenes de producción": "Seguimiento de trabajos.",
    "Mantenimiento del catálogo": "Actualización del catálogo.", "Reversos de producción": "Correcciones productivas.",
    "Inventario": "Existencias disponibles sin datos de compra.", "Movimientos de inventario": "Entradas y salidas.",
    "Ajustes de inventario": "Correcciones autorizadas.", "Alertas de inventario": "Mínimos y reposición.",
    "Costeo": "Costos y márgenes.", "Costeo por procesos": "Costos por etapa.", "BOM multinivel": "Materiales anidados.",
    "Tasas de cambio": "Tasas monetarias.", "Ajustar precios": "Actualización de precios.", "Exportar precios": "Listados de precios.",
    "Panel financiero y cierres": "Indicadores y cierres.", "Caja": "Ingresos y egresos.",
    "Conciliación financiera": "Validación financiera.", "Reabrir cierre de caja": "Reapertura autorizada.",
    "Gastos y presupuesto": "Gastos y planificación.", "Reversos de pagos": "Correcciones de pagos.",
    "Anulaciones y ajustes": "Rectificaciones auditadas.", "Estado de Resultados": "Rentabilidad del negocio.",
    "Flujo de caja proyectado": "Proyección de efectivo.", "RRHH y nómina": "Empleados y pagos.",
    "Equipo y comisiones": "Cálculo de comisiones.", "Historial de comisiones": "Consulta histórica.",
    "Activos": "Equipos y depreciación.", "Mantenimiento preventivo": "Calendario de máquinas.",
    "Usuarios y roles": "Accesos y permisos.", "Configuración General": "Parámetros del sistema.",
    "Respaldo general": "Copia integral del ERP.", "Respaldar activos": "Copia de activos.",
}

# Alias temporales para que las nuevas entradas del menú sean operativas mientras
# se separan en pantallas especializadas. Se reutilizan los flujos existentes y
# se evita duplicar la lógica que actualiza inventario, caja y respaldos.
FUNCTIONAL_PAGE_ALIASES = {
    "Recepción de mercancía": "Compras",
    "Catálogo de artículos": "Inventario",
}


def navigation_groups() -> dict[str, tuple[str, ...]]:
    """Devuelve la taxonomía canónica de áreas y páginas del ERP."""
    return {area: tuple(config[3]) for area, config in SPECIALTY_AREAS.items()}


def _app_shell():
    """Importa el shell de páginas solo después de definir la taxonomía."""
    from src import app_shell

    return app_shell


def _functional_page_name(selected_page: str) -> str:
    """Resuelve alias de navegación hacia un renderer funcional existente."""
    return FUNCTIONAL_PAGE_ALIASES.get(selected_page, selected_page)


def _page_is_allowed(page: str, allowed: set[str] | None) -> bool:
    """Autoriza una entrada por su nombre visible o por su módulo funcional."""
    if allowed is None or page == "Inicio":
        return True
    return page in allowed or _functional_page_name(page) in allowed


def _allowed_home_shortcuts(app_shell, allowed: set[str] | None):
    """Filtra accesos del Inicio con la misma regla del menú principal."""
    return tuple(
        shortcut
        for shortcut in app_shell._home_shortcuts()
        if _page_is_allowed(shortcut[3], allowed)
    )


def _allowed_home_alerts(app_shell, allowed: set[str] | None):
    """Construye solo alertas cuyo destino puede abrir el rol actual."""
    low_stock, expiring_lots = app_shell._inventory_alert_counts()
    alerts = (
        ("Cobros vencidos", app_shell._overdue_receivables(), "Revisa saldos cuya fecha de cobro ya pasó.", "Comercial y CRM", "Cuentas por cobrar"),
        ("Compras por recibir", app_shell._pending_purchase_receipts(), "Confirma mercancía pendiente de recepción.", "Compras y abastecimiento", "Recepción de mercancía"),
        ("Stock bajo", low_stock, "Atiende materiales en mínimo o agotados.", "Inventario y almacén", "Alertas de inventario"),
        ("Lotes próximos a vencer", expiring_lots, "Revisa lotes con vencimiento dentro de 30 días.", "Inventario y almacén", "Inventario"),
    )
    return tuple(alert for alert in alerts if _page_is_allowed(alert[4], allowed))


def _render_permission_aware_home(app_shell, allowed: set[str] | None) -> None:
    """Renderiza el Inicio sin exponer acciones hacia módulos restringidos."""
    clients, active_sales, low_stock, pending_payments = app_shell._home_metrics()
    app_shell.render_page_header(
        app_shell._home_greeting(),
        "Aquí tienes una vista rápida del negocio y los accesos principales para comenzar tu jornada.",
    )

    if _page_is_allowed("Novedades", allowed):
        with st.container(border=True):
            cols = st.columns([5, 1])
            cols[0].markdown("**🆕 Hay módulos nuevos**")
            cols[0].caption(
                "Catálogo de artículos, Recepción de mercancía, Venta rápida de mostrador, "
                "Estado de Resultados, Flujo de caja proyectado, RRHH y nómina, y Mantenimiento preventivo."
            )
            if cols[1].button("Ver todos", key="home_whats_new_button", use_container_width=True):
                app_shell._navigate("Inicio", "Novedades")

    metrics = st.columns(4)
    metrics[0].metric("Clientes registrados", str(clients))
    metrics[1].metric("Pedidos activos", str(active_sales))
    metrics[2].metric("Cobros pendientes", str(pending_payments))
    metrics[3].metric("Alertas de inventario", str(low_stock))

    if _page_is_allowed("Configuración General", allowed):
        app_shell._render_rates_cta()

    alerts = _allowed_home_alerts(app_shell, allowed)
    if alerts:
        st.markdown("### Alertas accionables")
        columns = st.columns(len(alerts))
        for index, (title, count, description, area, page) in enumerate(alerts):
            with columns[index]:
                st.metric(title, str(count))
                st.caption(description)
                if st.button("Revisar", key=f"home_alert_{index}", use_container_width=True):
                    app_shell._navigate(area, page)

    if _page_is_allowed("Respaldo general", allowed):
        st.markdown(
            '<div class="cm-home-note"><div><strong>Respaldo recomendado</strong><span>Guarda una copia antes de cerrar o reiniciar la aplicación.</span></div><div class="cm-home-note__badge">Protege tu trabajo</div></div>',
            unsafe_allow_html=True,
        )

    shortcuts = _allowed_home_shortcuts(app_shell, allowed)
    if shortcuts:
        st.markdown("### Accesos principales")
        st.caption("Pulsa Abrir para entrar directamente en la sección correspondiente.")
        columns = st.columns(min(3, len(shortcuts)))
        for index, (title, description, area, page) in enumerate(shortcuts):
            with columns[index % len(columns)]:
                app_shell.render_info_card(title, description, "ACCESO RÁPIDO")
                if st.button(
                    f"Abrir {title}",
                    key=f"home_shortcut_{index}",
                    use_container_width=True,
                    type="primary" if index == 0 else "secondary",
                ):
                    app_shell._navigate(area, page)

    st.markdown("### Estado general")
    status_columns = st.columns(2)
    with status_columns[0]:
        app_shell.render_info_card(
            "Operación",
            "El inicio resume pedidos, cobros e inventario para ayudarte a decidir qué atender primero.",
            "RESUMEN DIARIO",
        )
    with status_columns[1]:
        app_shell.render_info_card(
            "Seguridad de datos",
            "Los accesos del Inicio respetan los permisos asignados al rol actual.",
            "CONTROL DE ACCESO",
        )


def _effective_areas(user):
    app_shell = _app_shell()
    allowed = auth.allowed_modules_for_role(user.role_id, user.role_name)
    registered = set(app_shell.FUNCTIONAL_MODULES)
    registered.update(page for pages in navigation_groups().values() for page in pages)
    registered.add("Inicio")
    areas = {}
    for area, (icon, eyebrow, description, pages) in SPECIALTY_AREAS.items():
        visible = tuple(page for page in pages if page in registered and _page_is_allowed(page, allowed))
        if visible:
            areas[area] = (icon, eyebrow, description, visible)
    return areas or {"Inicio": SPECIALTY_AREAS["Inicio"]}, allowed


def _render_module_selector(area: str, pages: tuple[str, ...]) -> str:
    current = st.session_state.get("navigation_page")
    if current not in pages:
        current = pages[0]
        st.session_state["navigation_page"] = current
    if len(pages) == 1:
        return pages[0]
    selected = st.radio("Módulos del área", pages, index=pages.index(current), key=f"module_strip_{area}", horizontal=True, label_visibility="collapsed")
    if selected != current:
        st.session_state["navigation_page"] = selected
        st.rerun()
    st.markdown(f'<div class="cm-selected-module"><strong>{selected}</strong><span>{DESCRIPTIONS.get(selected, "Herramientas de esta especialidad.")}</span></div>', unsafe_allow_html=True)
    return selected


def _render_current_page(selected_page: str, allowed) -> None:
    app_shell = _app_shell()
    if not _page_is_allowed(selected_page, allowed):
        st.error("No tienes permiso para ver esta sección.")
        return
    st.markdown('<div class="cm-content-frame">', unsafe_allow_html=True)
    functional_page = _functional_page_name(selected_page)
    if selected_page == "Inicio":
        _render_permission_aware_home(app_shell, allowed)
    elif functional_page in app_shell.FUNCTIONAL_MODULES:
        app_shell.FUNCTIONAL_MODULES[functional_page]()
    else:
        app_shell.render_descriptive_module(selected_page)
    st.markdown('</div>', unsafe_allow_html=True)


def run_app() -> None:
    app_shell = _app_shell()
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
    st.markdown(f'<div class="cm-shell"><div class="cm-topline"><div class="cm-brand"><div class="cm-logo">CM</div><div><div class="cm-brand-title">CopyMary Enterprise</div><div class="cm-brand-subtitle">ERP integral para impresión, papelería y servicios</div></div></div><div class="cm-account"><span class="cm-account-dot"></span><div><div class="cm-account-name">{user.display_name}</div><div class="cm-account-role">{user.role_name}</div></div></div></div><div class="cm-nav-label">Áreas de especialidad</div></div>', unsafe_allow_html=True)
    nav, action = st.columns([10, 1])
    with nav:
        selected_area = st.radio("Áreas", tuple(areas), key="navigation_area", horizontal=True, label_visibility="collapsed")
    with action:
        if st.button("Salir", key="top_logout_button", use_container_width=True):
            auth.logout()
            st.rerun()
    icon, eyebrow, description, pages = areas[selected_area]
    st.markdown(f'<div class="cm-workspace"><div><div class="cm-eyebrow">{eyebrow}</div><div class="cm-workspace-title">{selected_area}</div><div class="cm-workspace-copy">{description}</div></div><div class="cm-workspace-icon">{icon}</div></div>', unsafe_allow_html=True)
    if selected_area != "Administración y seguridad":
        from src.payment_fees import rates_are_stale, rates_badge_html
        badge_html = rates_badge_html()
        if badge_html:
            st.markdown(badge_html, unsafe_allow_html=True)
        if rates_are_stale():
            st.warning("⚠️ Las tasas de cambio (BCV/Binance/Kontigo) no se han confirmado hoy. Ve a Administración y seguridad → Configuración General para revisarlas.")
    selected_page = _render_module_selector(selected_area, tuple(pages))
    _render_current_page(selected_page, allowed)
    st.markdown(f'<div class="cm-footer">Versión {APP_VERSION} · {PROJECT_STATUS} · Mantén respaldos periódicos de la información.</div>', unsafe_allow_html=True)