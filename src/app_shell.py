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


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _home_metrics() -> tuple[int, int, int, int]:
    clients = len(_rows("customers_registry"))
    sales = [
        item for item in _rows("sales_registry")
        if str(item.get("order_status", "")).strip().lower() not in {"cancelado", "cancelada", "anulado", "anulada"}
    ]
    active_sales = sum(
        1 for item in sales
        if str(item.get("order_status", "Pendiente")) not in {"Entregado", "Entregada"}
    )
    inventory = _rows("inventory_registry")
    low_stock = 0
    for item in inventory:
        try:
            available = float(item.get("available_quantity", item.get("quantity", 0.0)))
            minimum = float(item.get("minimum_stock", item.get("reorder_point", 0.0)))
        except (TypeError, ValueError):
            continue
        if minimum > 0 and available <= minimum:
            low_stock += 1
    pending_payments = sum(
        1 for item in sales
        if str(item.get("payment_status", "Pendiente")) != "Pagado"
    )
    return clients, active_sales, low_stock, pending_payments


def render_home() -> None:
    clients, active_sales, low_stock, pending_payments = _home_metrics()

    render_page_header(
        "Buenos días, Copy Mary",
        "Aquí tienes una vista rápida del negocio y los accesos principales para comenzar tu jornada.",
    )

    metrics = st.columns(4)
    metrics[0].metric("Clientes registrados", str(clients))
    metrics[1].metric("Pedidos activos", str(active_sales))
    metrics[2].metric("Cobros pendientes", str(pending_payments))
    metrics[3].metric("Alertas de inventario", str(low_stock))

    st.markdown(
        '<div class="cm-home-note"><div><strong>Respaldo recomendado</strong><span>Guarda una copia antes de cerrar o reiniciar la aplicación.</span></div><div class="cm-home-note__badge">Protege tu trabajo</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Accesos principales")
    st.caption("Las áreas más importantes para trabajar durante el día.")
    columns = st.columns(3)
    cards = (
        ("Centro de control", "Revisa alertas, pendientes y decisiones importantes del negocio."),
        ("Ventas y clientes", "Registra clientes, prepara cotizaciones y gestiona pedidos y cobros."),
        ("Productos e inventario", "Controla materiales, recetas, producción, costos y existencias."),
        ("Compras y proveedores", "Organiza abastecimiento, compras y pagos a proveedores."),
        ("Finanzas", "Consulta caja, gastos, cierres y el estado financiero del negocio."),
        ("Respaldos", "Descarga o restaura una copia segura de toda la información."),
    )
    for index, (title, description) in enumerate(cards):
        with columns[index % 3]:
            render_info_card(title, description, "ACCESO RÁPIDO")

    st.markdown("### Estado general")
    status_columns = st.columns(2)
    with status_columns[0]:
        render_info_card(
            "Operación",
            "El inicio resume pedidos, cobros e inventario para ayudarte a decidir qué atender primero.",
            "RESUMEN DIARIO",
        )
    with status_columns[1]:
        render_info_card(
            "Seguridad de datos",
            "La información vive en la sesión. Usa Respaldo general para conservarla de forma segura.",
            "RECORDATORIO",
        )


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
        .cm-home-note{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 1.15rem;margin:1.15rem 0 1.55rem;border-radius:16px;background:linear-gradient(135deg,rgba(34,166,161,.12),rgba(109,74,255,.08));border:1px solid rgba(34,166,161,.18);color:#334155}.cm-home-note>div:first-child{display:flex;flex-direction:column;gap:.2rem}.cm-home-note strong{color:#0f766e}.cm-home-note span{color:#64748b;font-size:.92rem}.cm-home-note__badge{padding:.42rem .7rem;border-radius:999px;background:white;color:#6D4AFF;font-size:.78rem;font-weight:800;box-shadow:0 5px 14px rgba(31,41,55,.07)}
        .cm-sidebrand{display:flex;align-items:center;gap:.8rem;padding:.45rem 0 1rem}.cm-sidebrand__mark{display:grid;place-items:center;width:44px;height:44px;border-radius:14px;background:linear-gradient(135deg,#6D4AFF,#22A6A1);color:white;font-weight:900;box-shadow:0 10px 22px rgba(109,74,255,.25)}.cm-sidebrand__name{font-weight:850;font-size:1.08rem;letter-spacing:-.02em;color:#1f2937}.cm-sidebrand__tag{font-size:.75rem;color:#7c8494;margin-top:.08rem}
        @media(max-width:768px){.cm-home-note{align-items:flex-start;flex-direction:column;gap:.6rem}.cm-home-note__badge{align-self:flex-start}}
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
