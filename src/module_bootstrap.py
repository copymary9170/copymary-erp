"""Registro central de módulos mejorados de CopyMary ERP."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Callable

from src import app_shell


logger = logging.getLogger(__name__)

MODULE_RENDERERS: tuple[tuple[str, str, str], ...] = (
    ("Novedades", "src.whats_new", "render_whats_new"),
    ("Centro de control", "src.control_center_today", "render_control_center_today"),
    ("Auditoría de datos", "src.data_audit_insights", "render_data_audit_insights"),
    ("Fundación técnica", "src.foundation_status", "render_foundation_status"),
    ("Panel comercial", "src.commercial_dashboard_intelligence", "render_commercial_dashboard_intelligence"),
    ("Panel financiero y cierres", "src.financial_dashboard_plus", "render_financial_dashboard_plus"),
    ("Clientes", "src.clients_followup", "render_clients_followup"),
    ("Comprobantes", "src.receipts_control", "render_receipts_control"),
    ("Inventario", "src.inventory_planning", "render_inventory_planning"),
    ("Movimientos de inventario", "src.inventory_movements_enterprise", "render_inventory_movements_enterprise"),
    ("Alertas de inventario", "src.stock_alerts_intelligence", "render_stock_alerts_intelligence"),
    ("Costeo", "src.costing_control", "render_costing_control"),
    ("Costeo por procesos", "src.bom_costing", "render_bom_costing"),
    ("Tasas de cambio", "src.exchange_rates", "render_exchange_rates"),
    ("Órdenes de producción", "src.production_orders", "render_production_orders"),
    ("BOM multinivel", "src.bom_multilevel", "render_bom_multilevel"),
    ("Ajustar precios", "src.price_adjustment_governance", "render_price_adjustment_governance"),
    ("Exportar precios", "src.price_io_governance", "render_price_io_governance"),
    ("Caja", "src.cash_governance", "render_cash_governance"),
    ("Conciliación financiera", "src.financial_reconciliation_control", "render_financial_reconciliation_control"),
    ("Reabrir cierre de caja", "src.cash_reopen_governance", "render_cash_reopen_governance"),
    ("Gastos y presupuesto", "src.expenses_budget_control", "render_expenses_budget_control"),
    ("Equipo y comisiones", "src.team_commission_governance", "render_team_commission_governance"),
    ("Historial de comisiones", "src.commission_history_governance", "render_commission_history_governance"),
    ("Reversos de pagos", "src.payment_reversals_governance", "render_payment_reversals_governance"),
    ("Anulaciones y ajustes", "src.adjustments_postcontrol", "render_adjustments_postcontrol"),
    ("Activos", "src.assets_control", "render_assets_control"),
    ("Usuarios y roles", "src.users_roles", "render_users_roles"),
    ("RRHH y nómina", "src.payroll", "render_payroll"),
    ("Estado de Resultados", "src.income_statement", "render_income_statement"),
    ("Flujo de caja proyectado", "src.cash_flow_forecast", "render_cash_flow_forecast"),
    ("Mantenimiento preventivo", "src.machine_maintenance", "render_machine_maintenance"),
    ("Ajustes de inventario", "src.inventory_adjustments", "render_inventory_adjustments"),
    ("Venta rápida de mostrador", "src.quick_sale", "render_quick_sale"),
)

SIDE_EFFECT_MODULES: tuple[str, ...] = (
    "src.accounts_receivable_plus_loader",
    "src.suppliers_intelligence_loader",
    "src.production_reversals_visible",
)

PRODUCTS_NAVIGATION: tuple[str, ...] = (
    # Producción del día a día
    "Catálogo y producción", "Órdenes de producción",
    # Costeo y precios
    "Costeo", "Costeo por procesos", "BOM multinivel", "Tasas de cambio",
    "Ajustar precios", "Exportar precios",
    # Inventario
    "Inventario", "Ajustes de inventario", "Movimientos de inventario", "Alertas de inventario",
    # Mantenimiento del catálogo y de máquinas
    "Mantenimiento del catálogo", "Mantenimiento preventivo", "Reversos de producción",
)

ADMIN_NAVIGATION: tuple[str, ...] = (
    # Caja y bancos (día a día)
    "Caja", "Conciliación financiera", "Reabrir cierre de caja",
    # Gastos y personal
    "Gastos y presupuesto", "RRHH y nómina",
    "Equipo y comisiones", "Historial de comisiones",
    # Ajustes y anulaciones
    "Reversos de pagos", "Anulaciones y ajustes",
    # Configuración y respaldos
    "Activos", "Respaldar activos", "Configuración General", "Respaldo general", "Usuarios y roles",
)


# Se llena en activate_module_bootstrap() con (nombre_visible, module_path,
# mensaje_de_error) por cada módulo que falló al cargar. Antes, un módulo
# roto simplemente desaparecía del menú sin que nadie se enterara — ver
# render_foundation_status() en foundation_status.py, que muestra esta lista
# a cualquier administrador que abra "Fundación técnica".
FAILED_MODULES: list[tuple[str, str, str]] = []


def _try_import(module_path: str, display_name: str = ""):
    try:
        return import_module(module_path)
    except Exception as exc:  # noqa: BLE001 - se registra, no se oculta
        logger.error("No se pudo cargar el módulo %s (%s): %s", module_path, display_name or "sin nombre visible", exc)
        FAILED_MODULES.append((display_name or module_path, module_path, str(exc)))
        return None


def _load_renderer(module_path: str, attr_name: str, display_name: str) -> Callable | None:
    module = _try_import(module_path, display_name)
    if module is None:
        return None
    renderer = getattr(module, attr_name, None)
    if renderer is None or not callable(renderer):
        message = f"El módulo cargó pero no tiene un renderer llamable '{attr_name}'."
        logger.error("%s (%s)", message, module_path)
        FAILED_MODULES.append((display_name, module_path, message))
        return None
    return renderer


def _merge_navigation(area: str, pages: tuple[str, ...]) -> None:
    """Agrega páginas a un grupo de navegación sin descartar las que ya
    haya puesto ahí otro módulo (p. ej. app_shell_goals.py). Antes esta
    función reemplazaba la tupla completa y así desaparecían del menú
    páginas que sí estaban registradas y funcionando en FUNCTIONAL_MODULES."""
    existing = app_shell.NAVIGATION_GROUPS.get(area, ())
    merged = list(existing)
    for page in pages:
        if page not in merged:
            merged.append(page)
    app_shell.NAVIGATION_GROUPS[area] = tuple(merged)


def activate_module_bootstrap() -> None:
    FAILED_MODULES.clear()
    for module_path in SIDE_EFFECT_MODULES:
        _try_import(module_path)
    for module_name, module_path, renderer_name in MODULE_RENDERERS:
        renderer = _load_renderer(module_path, renderer_name, module_name)
        if renderer is not None:
            app_shell.FUNCTIONAL_MODULES[module_name] = renderer
    _merge_navigation(
        "Inicio",
        (
            # Lo que se usa todos los días, primero
            "Inicio", "Novedades", "Venta rápida de mostrador",
            # Centro de mando
            "Centro de control", "Panel comercial", "Panel financiero y cierres",
            # Reportes gerenciales
            "Estado de Resultados", "Flujo de caja proyectado",
            # Herramientas técnicas
            "Auditoría de datos", "Fundación técnica",
        ),
    )
    _merge_navigation("Productos e inventario", PRODUCTS_NAVIGATION)
    _merge_navigation("Administración", ADMIN_NAVIGATION)

    status_module = _try_import("src.status_consistency", "Normalización de estados")
    if status_module is not None:
        normalizer = getattr(status_module, "normalize_session_statuses", None)
        if callable(normalizer):
            normalizer()
