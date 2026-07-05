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
    render_page_header(
        APP_NAME,
        "Tu centro de gestión para organizar ventas, producción, inventario, dinero y crecimiento sin perder la parte creativa del negocio.",
    )
    st.markdown(
        '<div class="cm-home-note"><strong>Sesión protegida por respaldo</strong><span>Descarga una copia antes de cerrar o reiniciar la aplicación.</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Todo tu negocio, organizado en un solo lugar")
    st.caption("Entra al área que necesites y continúa trabajando desde allí.")
    columns = st.columns(3)
    cards = (
        ("Centro de control", "Una vista rápida de alertas, pendientes y decisiones importantes."),
        ("Auditoría de datos", "Comprueba duplicados, referencias rotas y riesgos antes de que crezcan."),
        ("Ventas y clientes", "Gestiona clientes, cotizaciones, pedidos, cobros y comprobantes."),
        ("Compras y proveedores", "Organiza compras, proveedores y cuentas pendientes de pago."),
        ("Productos e inventario", "Controla materiales, recetas, costos, producción y existencias."),
        ("Administración", "Supervisa caja, gastos, equipo, activos, cierres y respaldos."),
    )
    for index, (title, description) in enumerate(cards):
        with columns[index % 3]:
            render_info_card(title, description, "ÁREA DE TRABAJO")


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
    st.markdown(
        """
        <style>
        .cm-home-note{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.9rem 1.1rem;margin:.2rem 0 1.4rem;border-radius:14px;background:linear-gradient(135deg,rgba(34,166,161,.11),rgba(109,74,255,.08));border:1px solid rgba(34,166,161,.18);color:#334155}.cm-home-note strong{color:#0f766e}.cm-home-note span{color:#64748b;font-size:.92rem}
        .cm-sidebrand{display:flex;align-items:center;gap:.8rem;padding:.45rem 0 1rem}.cm-sidebrand__mark{display:grid;place-items:center;width:44px;height:44px;border-radius:14px;background:linear-gradient(135deg,#6D4AFF,#22A6A1);color:white;font-weight:900;box-shadow:0 10px 22px rgba(109,74,255,.25)}.cm-sidebrand__name{font-weight:850;font-size:1.08rem;letter-spacing:-.02em;color:#1f2937}.cm-sidebrand__tag{font-size:.75rem;color:#7c8494;margin-top:.08rem}
        @media(max-width:768px){.cm-home-note{align-items:flex-start;flex-direction:column;gap:.25rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown(
            '<div class="cm-sidebrand"><div class="cm-sidebrand__mark">CM</div><div><div class="cm-sidebrand__name">CopyMary ERP</div><div class="cm-sidebrand__tag">Tu negocio, claro y organizado</div></div></div>',
            unsafe_allow_html=True,
        )
        selected_area = st.selectbox("Área de trabajo", tuple(NAVIGATION_GROUPS.keys()))
        selected_page = st.radio("Sección", NAVIGATION_GROUPS[selected_area])
        st.divider()
        st.caption(f"Versión {APP_VERSION} · {PROJECT_STATUS}")
        st.info("Guarda un respaldo general antes de cerrar la sesión.")

    if selected_page == "Inicio":
        render_home()
    elif selected_page in FUNCTIONAL_MODULES:
        FUNCTIONAL_MODULES[selected_page]()
    else:
        render_descriptive_module(selected_page)
