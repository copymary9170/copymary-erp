"""Interfaz principal de CopyMary ERP."""

import streamlit as st

from src.accounts_payable import render_accounts_payable
from src.accounts_receivable import render_accounts_receivable
from src.adjustments import render_adjustments
from src.assets import render_assets
from src.assets_backup import render_assets_backup
from src.catalog import render_catalog
from src.commercial import render_cash, render_clients, render_commercial_dashboard, render_sales
from src.commercial_documents import render_quotes, render_receipts
from src.commercial_reports import render_commercial_reports
from src.components import apply_base_styles, render_info_card, render_page_header
from src.config import APP_NAME, APP_VERSION, PROJECT_STATUS
from src.control_center import render_control_center
from src.costing import render_costing
from src.data_audit import render_data_audit
from src.expenses_budget import render_expenses_budget
from src.financial import render_financial_dashboard
from src.general_settings import render_general_settings
from src.inventory import render_inventory
from src.inventory_movements import render_inventory_movements
from src.modern_styles import apply_modern_styles
from src.modules import MODULES
from src.order_planning import render_order_planning
from src.price_export import render_price_export
from src.price_rounding import render_price_rounding
from src.purchasing import render_purchases, render_suppliers
from src.session_backup import render_session_backup
from src.stock_alerts import render_stock_alerts
from src.team_commissions import render_team_commissions

FUNCTIONAL_MODULES = {
    "Centro de control": render_control_center,
    "Auditoría de datos": render_data_audit,
    "Panel comercial": render_commercial_dashboard,
    "Panel financiero y cierres": render_financial_dashboard,
    "Clientes": render_clients,
    "Ventas y pedidos": render_sales,
    "Agenda de producción y entregas": render_order_planning,
    "Cuentas por cobrar": render_accounts_receivable,
    "Cotizaciones": render_quotes,
    "Comprobantes": render_receipts,
    "Caja": render_cash,
    "Gastos y presupuesto": render_expenses_budget,
    "Equipo y comisiones": render_team_commissions,
    "Anulaciones y ajustes": render_adjustments,
    "Reportes comerciales": render_commercial_reports,
    "Proveedores": render_suppliers,
    "Compras": render_purchases,
    "Cuentas por pagar": render_accounts_payable,
    "Catálogo y producción": render_catalog,
    "Inventario": render_inventory,
    "Movimientos de inventario": render_inventory_movements,
    "Alertas de inventario": render_stock_alerts,
    "Costeo": render_costing,
    "Ajustar precios": render_price_rounding,
    "Exportar precios": render_price_export,
    "Activos": render_assets,
    "Respaldar activos": render_assets_backup,
    "Configuración General": render_general_settings,
    "Respaldo general": render_session_backup,
}

NAVIGATION_GROUPS = {
    "Inicio": ("Inicio", "Centro de control", "Auditoría de datos", "Panel comercial", "Panel financiero y cierres"),
    "Ventas y clientes": ("Clientes", "Cotizaciones", "Ventas y pedidos", "Agenda de producción y entregas", "Cuentas por cobrar", "Comprobantes", "Reportes comerciales"),
    "Compras y proveedores": ("Proveedores", "Compras", "Cuentas por pagar"),
    "Productos e inventario": ("Catálogo y producción", "Inventario", "Movimientos de inventario", "Alertas de inventario", "Costeo", "Ajustar precios", "Exportar precios"),
    "Administración": ("Caja", "Gastos y presupuesto", "Equipo y comisiones", "Anulaciones y ajustes", "Activos", "Respaldar activos", "Configuración General", "Respaldo general"),
    "Planificación futura": tuple(name for name in MODULES if name not in FUNCTIONAL_MODULES),
}


def render_home() -> None:
    st.markdown(
        '<section class="cm-hero">'
        '<div class="cm-hero-kicker">COPYMARY ERP · PANEL PRINCIPAL</div>'
        '<h1>Todo tu negocio, en un solo lugar.</h1>'
        '<p>Controla ventas, compras, inventario, producción y finanzas desde una interfaz clara, conectada y pensada para Copy Mary.</p>'
        '<div class="cm-badges">'
        '<span class="cm-badge">Ventas conectadas</span>'
        '<span class="cm-badge">Inventario controlado</span>'
        '<span class="cm-badge">Finanzas conciliadas</span>'
        '</div></section>',
        unsafe_allow_html=True,
    )
    st.warning("Los datos viven en esta sesión. Descarga un respaldo antes de cerrar o reiniciar la aplicación.")
    st.subheader("Accesos principales")
    columns = st.columns(3)
    cards = (
        ("Centro de control", "Alertas, pendientes y estado general del negocio."),
        ("Auditoría de datos", "Duplicados, referencias rotas y controles de integridad."),
        ("Ventas y clientes", "Cotizaciones, pedidos, pagos y seguimiento comercial."),
        ("Compras y proveedores", "Abastecimiento, proveedores y cuentas por pagar."),
        ("Productos e inventario", "Recetas, costos, producción y existencias."),
        ("Administración", "Caja, gastos, equipo, activos y respaldos."),
    )
    for index, (title, description) in enumerate(cards):
        with columns[index % 3]:
            render_info_card(title, description, "ÁREA CLAVE")


def render_descriptive_module(name: str) -> None:
    info = MODULES.get(name)
    if info is None:
        st.error("La sección solicitada no está disponible.")
        return
    render_page_header(name, info["description"])
    st.warning("Esta pantalla todavía no ejecuta operaciones ni guarda datos.")
    render_info_card("Estado", info["status"], "SITUACIÓN ACTUAL")
    render_info_card("Objetivo", info["objective"], "PROPÓSITO")
    for function in info["planned_functions"]:
        st.markdown(f"- {function}")


def run_app() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="CM", layout="wide", initial_sidebar_state="expanded")
    apply_base_styles()
    apply_modern_styles()
    with st.sidebar:
        st.markdown(
            '<div class="cm-brand">'
            '<div class="cm-brand-mark">CM</div>'
            '<div><div class="cm-brand-name">CopyMary ERP</div>'
            '<div class="cm-brand-sub">Gestión creativa y ordenada</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        selected_area = st.selectbox("Área de trabajo", tuple(NAVIGATION_GROUPS.keys()))
        selected_page = st.radio("Sección", NAVIGATION_GROUPS[selected_area])
        st.caption(f"Versión {APP_VERSION} · {PROJECT_STATUS}")
        st.info("Usa Respaldo general antes de cerrar la sesión.")

    if selected_page == "Inicio":
        render_home()
    elif selected_page in FUNCTIONAL_MODULES:
        FUNCTIONAL_MODULES[selected_page]()
    else:
        render_descriptive_module(selected_page)
