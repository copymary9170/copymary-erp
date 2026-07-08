"""Registro central de módulos mejorados de CopyMary ERP.

Mantiene `app.py` estable para reducir conflictos entre PRs.
Cada mejora se registra aquí de forma defensiva: si un módulo todavía no existe,
la aplicación continúa usando la versión base ya registrada por `app_shell_payments`.
"""

from __future__ import annotations

from importlib import import_module
from typing import Callable

from src import app_shell


MODULE_RENDERERS: tuple[tuple[str, str, str], ...] = (
    ("Centro de control", "src.control_center_today", "render_control_center_today"),
    ("Auditoría de datos", "src.data_audit_insights", "render_data_audit_insights"),
    ("Panel comercial", "src.commercial_dashboard_intelligence", "render_commercial_dashboard_intelligence"),
    ("Panel financiero y cierres", "src.financial_dashboard_plus", "render_financial_dashboard_plus"),
    ("Clientes", "src.clients_followup", "render_clients_followup"),
    ("Comprobantes", "src.receipts_control", "render_receipts_control"),
    ("Inventario", "src.inventory_planning", "render_inventory_planning"),
    ("Movimientos de inventario", "src.inventory_movements_enterprise", "render_inventory_movements_enterprise"),
    ("Alertas de inventario", "src.stock_alerts_intelligence", "render_stock_alerts_intelligence"),
    ("Costeo", "src.costing_control", "render_costing_control"),
    ("Ajustar precios", "src.price_adjustment_governance", "render_price_adjustment_governance"),
    ("Exportar precios", "src.price_io_governance", "render_price_io_governance"),
    ("Caja", "src.cash_governance", "render_cash_governance"),
    ("Conciliación financiera", "src.financial_reconciliation", "render_financial_reconciliation"),
)

SIDE_EFFECT_MODULES: tuple[str, ...] = (
    "src.accounts_receivable_plus_loader",
    "src.suppliers_intelligence_loader",
    "src.production_reversals_visible",
)


PRODUCTS_NAVIGATION: tuple[str, ...] = (
    "Catálogo y producción",
    "Mantenimiento del catálogo",
    "Reversos de producción",
    "Inventario",
    "Movimientos de inventario",
    "Alertas de inventario",
    "Costeo",
    "Ajustar precios",
    "Exportar precios",
)

ADMIN_NAVIGATION: tuple[str, ...] = (
    "Caja",
    "Conciliación financiera",
    "Reabrir cierre de caja",
    "Gastos y presupuesto",
    "Equipo y comisiones",
    "Historial de comisiones",
    "Reversos de pagos",
    "Anulaciones y ajustes",
    "Activos",
    "Respaldar activos",
    "Configuración General",
    "Respaldo general",
)


def _try_import(module_path: str):
    try:
        return import_module(module_path)
    except Exception:
        return None


def _load_renderer(module_path: str, attr_name: str) -> Callable | None:
    module = _try_import(module_path)
    if module is None:
        return None
    renderer = getattr(module, attr_name, None)
    return renderer if callable(renderer) else None


def activate_module_bootstrap() -> None:
    """Registra módulos mejorados sin tocar `app.py` en cada PR."""
    for module_path in SIDE_EFFECT_MODULES:
        _try_import(module_path)

    for module_name, module_path, renderer_name in MODULE_RENDERERS:
        renderer = _load_renderer(module_path, renderer_name)
        if renderer is not None:
            app_shell.FUNCTIONAL_MODULES[module_name] = renderer

    app_shell.NAVIGATION_GROUPS["Productos e inventario"] = PRODUCTS_NAVIGATION
    app_shell.NAVIGATION_GROUPS["Administración"] = ADMIN_NAVIGATION
