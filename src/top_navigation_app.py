"""Interfaz empresarial con navegación superior por especialidad."""

import streamlit as st

from src import app_shell, app_shell_payments, auth
from src.components import apply_base_styles
from src.config import APP_NAME, APP_VERSION, PROJECT_STATUS
from src.modern_styles import apply_modern_styles


SPECIALTY_AREAS = {
    "Inicio": {
        "description": "Resumen ejecutivo, alertas y accesos de uso diario.",
        "pages": ("Inicio", "Novedades", "Centro de control", "Metas del negocio", "Panel comercial", "Auditoría de datos", "Fundación técnica"),
    },
    "Comercial y CRM": {
        "description": "Clientes, cotizaciones, ventas, pedidos y cobros.",
        "pages": ("Clientes", "Cotizaciones", "Ventas y pedidos", "Venta rápida de mostrador", "Agenda de producción y entregas", "Cuentas por cobrar", "Comprobantes", "Reportes comerciales"),
    },
    "Compras y abastecimiento": {
        "description": "Proveedores, compras, recepción y cuentas por pagar.",
        "pages": ("Proveedores", "Compras", "Cuentas por pagar"),
    },
    "Producción": {
        "description": "Catálogo productivo, órdenes, capacidad y reversos.",
        "pages": ("Catálogo y producción", "Órdenes de producción", "Mantenimiento del catálogo", "Reversos de producción"),
    },
    "Inventario y almacén": {
        "description": "Existencias, movimientos, ajustes y alertas de stock.",
        "pages": ("Inventario", "Movimientos de inventario", "Ajustes de inventario", "Alertas de inventario"),
    },
    "Costos y precios": {
        "description": "Costeo, recetas, márgenes, tasas y precios de venta.",
        "pages": ("Costeo", "Costeo por procesos", "BOM multinivel", "Tasas de cambio", "Ajustar precios", "Exportar precios"),
    },
    "Finanzas y tesorería": {
        "description": "Caja, conciliación, gastos, pagos, ajustes y cierres.",
        "pages": ("Panel financiero y cierres", "Caja", "Conciliación financiera", "Reabrir cierre de caja", "Gastos y presupuesto", "Reversos de pagos", "Anulaciones y ajustes"),
    },
    "Contabilidad y análisis": {
        "description": "Resultados financieros y proyecciones de efectivo.",
        "pages": ("Estado de Resultados", "Flujo de caja proyectado"),
    },
    "Talento humano": {
        "description": "Empleados, nómina, equipo y comisiones.",
        "pages": ("RRHH y nómina", "Equipo y comisiones", "Historial de comisiones"),
    },
    "Activos y mantenimiento": {
        "description": "Equipos, depreciación y mantenimiento preventivo.",
        "pages": ("Activos", "Mantenimiento preventivo"),
    },
    "Administración y seguridad": {
        "description": "Usuarios, roles, permisos y configuración general.",
        "pages": ("Usuarios y roles", "Configuración General"),
    },
    "Respaldos": {
        "description": "Copias de seguridad y restauración de información.",
        "pages": ("Respaldo general", "Respaldar activos"),
    },
}

DESCRIPTIONS = {
    "Inicio": "Vista general del negocio.",
    "Clientes": "Registro y seguimiento de clientes.",
    "Cotizaciones": "Presupuestos y seguimiento comercial.",
    "Ventas y pedidos": "Pedidos desde el registro hasta la entrega.",
    "Venta rápida de mostrador": "Venta directa y cobro inmediato.",
    "Proveedores": "Directorio y evaluación de proveedores.",
    "Compras": "Abastecimiento, recepción y control de compras.",
    "Cuentas por pagar": "Vencimientos y obligaciones pendientes.",
    "Catálogo y producción": "Productos, servicios, recetas y procesos.",
    "Órdenes de producción": "Ejecución y seguimiento de trabajos.",
    "Inventario": "Existencias y disponibilidad de materiales.",
    "Movimientos de inventario": "Entradas, salidas y trazabilidad.",
    "Ajustes de inventario": "Correcciones autorizadas de existencias.",
    "Alertas de inventario": "Mínimos y necesidades de reposición.",
    "Costeo": "Costos, consumos y márgenes.",
    "Costeo por procesos": "Costos detallados por etapa.",
    "BOM multinivel": "Materiales y componentes anidados.",
    "Tasas de cambio": "Tasas monetarias aplicables.",
    "Ajustar precios": "Actualización controlada de precios.",
    "Exportar precios": "Listados y archivos de precios.",
    "Panel financiero y cierres": "Indicadores y cierres financieros.",
    "Caja": "Ingresos, egresos y movimientos diarios.",
    "Conciliación financiera": "Validación de movimientos financieros.",
    "Gastos y presupuesto": "Gastos, límites y planificación.",
    "Estado de Resultados": "Ingresos, costos, gastos y rentabilidad.",
    "Flujo de caja proyectado": "Proyección de efectivo a futuro.",
    "RRHH y nómina": "Empleados, períodos y recibos de pago.",
    "Equipo y comisiones": "Asignación y cálculo de comisiones.",
    "Activos": "Equipos, depreciación y patrimonio.",
    "Mantenimiento preventivo": "Calendario y bitácora de máquinas.",
    "Usuarios y roles": "Accesos, roles y permisos.",
    "Configuración General": "Parámetros del sistema y del negocio.",
    "Respaldo general": "Copia y restauración integral del ERP.",
    "Respaldar activos": "Respaldo específico de activos.",
}


def _apply_styles():
    st.markdown("""
    <style>
    [data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important}
    .block-container{padding:1rem 1.6rem 3rem;max-width:1680px}
    .cm-header{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 1.15rem;margin-bottom:.8rem;border:1px solid rgba(109,74,255,.14);border-radius:22px;background:linear-gradient(135deg,#fff,#faf8ff 60%,#f2fbfa);box-shadow:0 16px 45px rgba(30,41,59,.08)}
    .cm-brand{display:flex;align-items:center;gap:.85rem}.cm-logo{display:grid;place-items:center;width:48px;height:48px;border-radius:16px;background:linear-gradient(135deg,#6D4AFF,#8B5CF6,#22A6A1);color:#fff;font-weight:900;box-shadow:0 12px 25px rgba(109,74,255,.25)}
    .cm-title{font-size:1.17rem;font-weight:900;color:#172033}.cm-subtitle{font-size:.78rem;color:#778197}.cm-user{font-size:.8rem;color:#5f697b;padding:.5rem .75rem;border-radius:13px;background:#fff;border:1px solid rgba(109,74,255,.12)}
    .cm-area{padding:1rem 1.1rem;margin:.7rem 0 1rem;border-radius:18px;background:linear-gradient(110deg,rgba(109,74,255,.10),rgba(34,166,161,.08));border:1px solid rgba(109,74,255,.13)}
    .cm-area strong{display:block;color:#253047;font-size:1.05rem}.cm-area span{color:#6c7688;font-size:.84rem}
    div[data-testid="stRadio"]>div{gap:.35rem;flex-wrap:wrap}div[data-testid="stRadio"] label{background:#fff;border:1px solid rgba(109,74,255,.15);border-radius:999px;padding:.46rem .75rem;box-shadow:0 3px 10px rgba(30,41,59,.04)}
    div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:18px!important;border-color:rgba(109,74,255,.14)!important;background:linear-gradient(180deg,#fff,#fdfcff);box-shadow:0 7px 22px rgba(30,41,59,.045)}
    div[data-testid="stButton"] button{min-height:2.55rem;border-radius:12px;font-weight:700}.cm-card-title{font-weight:850;color:#253047}.cm-card-copy{font-size:.79rem;color:#6c7688;min-height:2.3rem;line-height:1.4}.cm-kicker{font-size:.68rem;font-weight:850;letter-spacing:.08em;color:#8b5cf6;text-transform:uppercase}
    @media(max-width:900px){.block-container{padding:.7rem .8rem 2rem}.cm-header{align-items:flex-start;flex-direction:column}.cm-user{width:100%}}
    </style>""", unsafe_allow_html=True)


def _effective_areas(user):
    allowed = auth.allowed_modules_for_role(user.role_id, user.role_name)
    registered = set(app_shell.FUNCTIONAL_MODULES)
    for pages in app_shell.NAVIGATION_GROUPS.values():
        registered.update(pages)
    registered.add("Inicio")
    areas = {}
    for area, data in SPECIALTY_AREAS.items():
        pages = tuple(page for page in data["pages"] if page in registered and (allowed is None or page == "Inicio" or page in allowed))
        if pages:
            areas[area] = {"description": data["description"], "pages": pages}
    return areas or {"Inicio": SPECIALTY_AREAS["Inicio"]}, allowed


def _render_cards(area, pages):
    current = st.session_state.get("navigation_page")
    if current not in pages:
        current = pages[0]
        st.session_state["navigation_page"] = current
    if len(pages) == 1:
        return pages[0]
    columns = st.columns(3)
    for index, page in enumerate(pages):
        with columns[index % 3]:
            with st.container(border=True):
                active = page == current
                st.markdown(f'<div class="cm-kicker">{"Sección activa" if active else "Módulo"}</div><div class="cm-card-title">{page}</div><div class="cm-card-copy">{DESCRIPTIONS.get(page, "Herramientas y operaciones de esta especialidad.")}</div>', unsafe_allow_html=True)
                if st.button("Abierto" if active else "Abrir módulo", key=f"specialty_{area}_{page}", use_container_width=True, type="primary" if active else "secondary", disabled=active):
                    st.session_state["navigation_page"] = page
                    st.rerun()
    return st.session_state["navigation_page"]


def run_app():
    st.set_page_config(page_title=APP_NAME, page_icon="CM", layout="wide", initial_sidebar_state="collapsed")
    apply_base_styles(); apply_modern_styles(); _apply_styles(); app_shell._apply_pending_navigation()
    if not auth.require_login():
        return
    user = auth.current_user()
    areas, allowed = _effective_areas(user)
    st.markdown(f'<div class="cm-header"><div class="cm-brand"><div class="cm-logo">CM</div><div><div class="cm-title">CopyMary Enterprise ERP</div><div class="cm-subtitle">Gestión empresarial integrada por áreas de especialidad</div></div></div><div class="cm-user">{user.display_name} · {user.role_name}</div></div>', unsafe_allow_html=True)
    nav, action = st.columns([9,1])
    st.session_state.setdefault("navigation_area", "Inicio")
    if st.session_state["navigation_area"] not in areas:
        st.session_state["navigation_area"] = next(iter(areas))
    with nav:
        selected_area = st.radio("Áreas", tuple(areas), key="navigation_area", horizontal=True, label_visibility="collapsed")
    with action:
        if st.button("Salir", use_container_width=True):
            auth.logout(); st.rerun()
    data = areas[selected_area]
    st.markdown(f'<div class="cm-area"><strong>{selected_area}</strong><span>{data["description"]}</span></div>', unsafe_allow_html=True)
    selected_page = _render_cards(selected_area, tuple(data["pages"]))
    st.divider()
    if allowed is not None and selected_page != "Inicio" and selected_page not in allowed:
        st.error("No tienes permiso para ver esta sección."); return
    if selected_page == "Inicio":
        app_shell.render_home()
    elif selected_page in app_shell.FUNCTIONAL_MODULES:
        app_shell.FUNCTIONAL_MODULES[selected_page]()
    else:
        app_shell.render_descriptive_module(selected_page)
    st.caption(f"Versión {APP_VERSION} · {PROJECT_STATUS} · Guarda respaldos periódicos.")
