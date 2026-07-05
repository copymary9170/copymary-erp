"""Extensión de navegación para metas y controles operativos."""

from src import app_shell, session_backup
from src.business_goals import render_business_goals
from src.catalog_maintenance import render_catalog_maintenance
from src.catalog_safe import render_safe_catalog
from src.financial_control import render_financial_control
from src.production_reversal import render_production_reversal
from src.purchase_receipt_control import activate_purchase_trace, render_purchases_with_trace
from src.team_commission_control import render_team_commission_control


activate_purchase_trace()
if "commission_assignments" not in session_backup.LIST_SECTIONS:
    session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, "commission_assignments")
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)
    session_backup.SECTION_LABELS["commission_assignments"] = "Asignaciones de comisión"

app_shell.FUNCTIONAL_MODULES["Metas del negocio"] = render_business_goals
app_shell.FUNCTIONAL_MODULES["Panel financiero y cierres"] = render_financial_control
app_shell.FUNCTIONAL_MODULES["Compras"] = render_purchases_with_trace
app_shell.FUNCTIONAL_MODULES["Equipo y comisiones"] = render_team_commission_control
app_shell.FUNCTIONAL_MODULES["Catálogo y producción"] = render_safe_catalog
app_shell.FUNCTIONAL_MODULES["Mantenimiento del catálogo"] = render_catalog_maintenance
app_shell.FUNCTIONAL_MODULES["Reversos de producción"] = render_production_reversal
app_shell.NAVIGATION_GROUPS["Inicio"] = (
    "Inicio",
    "Centro de control",
    "Auditoría de datos",
    "Metas del negocio",
    "Panel comercial",
    "Panel financiero y cierres",
)
app_shell.NAVIGATION_GROUPS["Productos e inventario"] = (
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


def run_app() -> None:
    app_shell.run_app()
