"""Interfaz principal de CopyMary ERP."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st

from src import auth
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
from src.payment_fees import rates_are_stale
from src.price_export import render_price_export
from src.price_rounding import render_price_rounding
from src.purchasing import render_purchases, render_suppliers
from src.session_backup import render_session_backup
from src.stock_alerts import render_stock_alerts
from src.team_commissions import render_team_commissions
from src.session_utils import read_list as _rows

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


def navigation_groups() -> dict[str, tuple[str, ...]]:
    """Obtiene la taxonomía activa sin duplicarla dentro de este shell."""
    from src.top_navigation_app import navigation_groups as active_navigation_groups

    return active_navigation_groups()


NAVIGATION_GROUPS = navigation_groups()


def _is_navigation_target(area: str | None, page: str | None) -> bool:
    groups = navigation_groups()
    return bool(area in groups and page in groups[area])


def _navigate(area: str, page: str) -> None:
    """Solicita un cambio de navegación para aplicarlo antes de crear widgets."""
    if not _is_navigation_target(area, page):
        st.error("El acceso rápido solicitado no está disponible.")
        return
    st.session_state["pending_navigation_area"] = area
    st.session_state["pending_navigation_page"] = page
    st.rerun()


def go_to(page: str) -> None:
    """Navega a una página buscando automáticamente su área activa."""
    for area, pages in navigation_groups().items():
        if page in pages:
            _navigate(area, page)
            return
    st.error(f"La sección '{page}' no está disponible en el menú.")


def _apply_pending_navigation() -> None:
    """Aplica cambios pendientes antes de instanciar selectbox y radio."""
    area = st.session_state.pop("pending_navigation_area", None)
    page = st.session_state.pop("pending_navigation_page", None)
    if _is_navigation_target(area, page):
        st.session_state["navigation_area"] = area
        st.session_state["navigation_page"] = page


def _greeting_for_hour(hour: int) -> str:
    """Devuelve el saludo correspondiente a una hora local de 0 a 23."""
    if not 0 <= hour <= 23:
        raise ValueError("La hora debe estar entre 0 y 23.")
    if hour < 12:
        return "Buenos días"
    if hour < 19:
        return "Buenas tardes"
    return "Buenas noches"


def _home_greeting(now: datetime | None = None) -> str:
    current = now or datetime.now().astimezone()
    user = auth.current_user()
    display_name = user.display_name.strip() if user and user.display_name.strip() else ""
    greeting = _greeting_for_hour(current.hour)
    return f"{greeting}, {display_name}" if display_name else greeting


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _active_sales() -> list[dict]:
    cancelled = {"cancelado", "cancelada", "anulado", "anulada"}
    return [
        item
        for item in _rows("sales_registry")
        if str(item.get("order_status", "")).strip().casefold() not in cancelled
    ]


def _paid_amount(sale: dict, payments: list[dict]) -> float:
    sale_id = str(sale.get("sale_id", ""))
    registered = sum(
        _safe_float(payment.get("amount"))
        for payment in payments
        if str(payment.get("sale_id", "")) == sale_id
    )
    total = _safe_float(sale.get("total"))
    if registered > 0:
        return min(registered, total)
    if sale.get("payment_status") == "Pagado" and sale.get("cash_registered"):
        return total
    return 0.0


def _overdue_receivables(today: date | None = None) -> int:
    current_date = today or date.today()
    metadata = {
        str(item.get("sale_id", "")): item
        for item in _rows("receivables_registry")
    }
    payments = _rows("payment_records")
    overdue = 0
    for sale in _active_sales():
        balance = max(_safe_float(sale.get("total")) - _paid_amount(sale, payments), 0.0)
        due_date = str(metadata.get(str(sale.get("sale_id", "")), {}).get("due_date", ""))
        if balance <= 0 or not due_date:
            continue
        try:
            if date.fromisoformat(due_date) < current_date:
                overdue += 1
        except ValueError:
            continue
    return overdue


def _pending_purchase_receipts() -> int:
    return sum(
        1
        for item in _rows("purchases_registry")
        if str(item.get("receipt_status", "Pendiente")).strip().casefold() == "pendiente"
    )


def _inventory_alert_counts(today: date | None = None, days_ahead: int = 30) -> tuple[int, int]:
    current_date = today or date.today()
    expiry_limit = current_date + timedelta(days=days_ahead)
    low_stock = 0
    expiring_lots = 0
    for item in _rows("inventory_registry"):
        available = _safe_float(item.get("available_quantity", item.get("quantity")))
        minimum = _safe_float(item.get("minimum_stock", item.get("reorder_point")))
        if minimum > 0 and available <= minimum:
            low_stock += 1
        expiry_value = item.get("expiration_date") or item.get("expiry_date") or item.get("fecha_vencimiento")
        if not expiry_value:
            continue
        try:
            expiry_date = date.fromisoformat(str(expiry_value)[:10])
        except ValueError:
            continue
        if current_date <= expiry_date <= expiry_limit:
            expiring_lots += 1
    return low_stock, expiring_lots


def _home_metrics() -> tuple[int, int, int, int]:
    clients = len(_rows("customers_registry"))
    sales = _active_sales()
    active_sales = sum(
        1
        for item in sales
        if str(item.get("order_status", "Pendiente")) not in {"Entregado", "Entregada"}
    )
    low_stock, _ = _inventory_alert_counts()
    pending_payments = sum(
        1 for item in sales if str(item.get("payment_status", "Pendiente")) != "Pagado"
    )
    return clients, active_sales, low_stock, pending_payments


def _home_shortcuts() -> tuple[tuple[str, str, str, str], ...]:
    return (
        ("Centro de control", "Revisa alertas, pendientes y decisiones importantes del negocio.", "Inicio", "Centro de control"),
        ("Ventas y pedidos", "Gestiona clientes, pedidos, entregas y cobros.", "Comercial y CRM", "Ventas y pedidos"),
        ("Catálogo e inventario", "Controla productos, materiales y existencias.", "Inventario y almacén", "Inventario"),
        ("Compras", "Organiza proveedores y órdenes de abastecimiento.", "Compras y abastecimiento", "Compras"),
        ("Panel financiero", "Consulta caja, gastos, cierres y resultados financieros.", "Finanzas y tesorería", "Panel financiero y cierres"),
        ("Respaldo general", "Descarga o restaura una copia segura de la información.", "Respaldos", "Respaldo general"),
        ("Recepción de mercancía", "Confirma lo recibido y actualiza existencias.", "Compras y abastecimiento", "Recepción de mercancía"),
        ("Catálogo de artículos", "Administra la definición maestra de materiales y productos.", "Inventario y almacén", "Catálogo de artículos"),
    )


def _render_actionable_alerts() -> None:
    overdue = _overdue_receivables()
    pending_receipts = _pending_purchase_receipts()
    low_stock, expiring_lots = _inventory_alert_counts()
    alerts = (
        ("Cobros vencidos", overdue, "Revisa saldos cuya fecha de cobro ya pasó.", "Comercial y CRM", "Cuentas por cobrar"),
        ("Compras por recibir", pending_receipts, "Confirma mercancía pendiente de recepción.", "Compras y abastecimiento", "Recepción de mercancía"),
        ("Stock bajo", low_stock, "Atiende materiales en mínimo o agotados.", "Inventario y almacén", "Alertas de inventario"),
        ("Lotes próximos a vencer", expiring_lots, "Revisa lotes con vencimiento dentro de 30 días.", "Inventario y almacén", "Inventario"),
    )
    st.markdown("### Alertas accionables")
    columns = st.columns(4)
    for index, (title, count, description, area, page) in enumerate(alerts):
        with columns[index]:
            st.metric(title, str(count))
            st.caption(description)
            if st.button("Revisar", key=f"home_alert_{index}", use_container_width=True):
                _navigate(area, page)


def _render_rates_cta() -> None:
    if not rates_are_stale():
        return
    with st.container(border=True):
        columns = st.columns([5, 1])
        columns[0].warning("Las tasas BCV, Binance y Kontigo todavía no han sido confirmadas hoy.")
        if columns[1].button("Confirmar tasas", key="home_rates_cta", use_container_width=True, type="primary"):
            _navigate("Administración y seguridad", "Configuración General")


def render_home() -> None:
    clients, active_sales, low_stock, pending_payments = _home_metrics()

    render_page_header(
        _home_greeting(),
        "Aquí tienes una vista rápida del negocio y los accesos principales para comenzar tu jornada.",
    )

    with st.container(border=True):
        cols = st.columns([5, 1])
        cols[0].markdown("**🆕 Hay módulos nuevos**")
        cols[0].caption(
            "Catálogo de artículos, Recepción de mercancía, Venta rápida de mostrador, "
            "Estado de Resultados, Flujo de caja proyectado, RRHH y nómina, y Mantenimiento preventivo."
        )
        if cols[1].button("Ver todos", key="home_whats_new_button", use_container_width=True):
            _navigate("Inicio", "Novedades")

    metrics = st.columns(4)
    metrics[0].metric("Clientes registrados", str(clients))
    metrics[1].metric("Pedidos activos", str(active_sales))
    metrics[2].metric("Cobros pendientes", str(pending_payments))
    metrics[3].metric("Alertas de inventario", str(low_stock))

    _render_rates_cta()
    _render_actionable_alerts()

    st.markdown(
        '<div class="cm-home-note"><div><strong>Respaldo recomendado</strong><span>Guarda una copia antes de cerrar o reiniciar la aplicación.</span></div><div class="cm-home-note__badge">Protege tu trabajo</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Accesos principales")
    st.caption("Pulsa Abrir para entrar directamente en la sección correspondiente.")
    columns = st.columns(3)
    for index, (title, description, area, page) in enumerate(_home_shortcuts()):
        with columns[index % 3]:
            render_info_card(title, description, "ACCESO RÁPIDO")
            if st.button(
                f"Abrir {title}",
                key=f"home_shortcut_{index}",
                use_container_width=True,
                type="primary" if index == 0 else "secondary",
            ):
                _navigate(area, page)

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

    _apply_pending_navigation()

    if not auth.require_login():
        return

    user = auth.current_user()
    allowed_modules = auth.allowed_modules_for_role(user.role_id, user.role_name)
    groups = navigation_groups()

    if allowed_modules is None:
        effective_groups = groups
    else:
        effective_groups = {}
        for area, pages in groups.items():
            kept = tuple(page for page in pages if page == "Inicio" or page in allowed_modules)
            if kept:
                effective_groups[area] = kept
        if not effective_groups:
            effective_groups = {"Inicio": ("Inicio",)}

    st.session_state.setdefault("navigation_area", "Inicio")
    if st.session_state["navigation_area"] not in effective_groups:
        st.session_state["navigation_area"] = next(iter(effective_groups))
    valid_pages = effective_groups[st.session_state["navigation_area"]]
    if st.session_state.get("navigation_page") not in valid_pages:
        st.session_state["navigation_page"] = valid_pages[0]

    with st.sidebar:
        st.markdown(
            '<div class="cm-sidebrand"><div class="cm-sidebrand__mark">CM</div><div><div class="cm-sidebrand__name">CopyMary ERP</div><div class="cm-sidebrand__tag">Tu negocio, claro y organizado</div></div></div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Sesión: {user.display_name} · {user.role_name}")
        if st.button("Cerrar sesión", use_container_width=True, key="logout_button"):
            auth.logout()
            st.rerun()
        selected_area = st.selectbox(
            "Área de trabajo",
            tuple(effective_groups.keys()),
            key="navigation_area",
        )
        available_pages = effective_groups[selected_area]
        if st.session_state.get("navigation_page") not in available_pages:
            st.session_state["navigation_page"] = available_pages[0]
        selected_page = st.radio(
            "Sección",
            available_pages,
            key="navigation_page",
        )
        st.divider()
        st.caption(f"Versión {APP_VERSION} · {PROJECT_STATUS}")
        st.info("Guarda un respaldo general antes de cerrar la sesión.")

    if allowed_modules is not None and selected_page != "Inicio" and selected_page not in allowed_modules:
        st.error("No tienes permiso para ver esta sección. Pide acceso a un administrador.")
        return

    if selected_page == "Inicio":
        render_home()
    elif selected_page in FUNCTIONAL_MODULES:
        FUNCTIONAL_MODULES[selected_page]()
    else:
        render_descriptive_module(selected_page)
