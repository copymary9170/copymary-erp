"""Extensión de renderers para metas y controles operativos."""

from src import app_shell, session_backup
from src.business_goals_plus import render_business_goals_plus
from src.catalog_maintenance import render_catalog_maintenance
from src.catalog_safe import render_safe_catalog
from src.executive_dashboard_integration import activate_executive_dashboard
from src.financial_control import render_financial_control
from src.production_reversal import render_production_reversal
from src.purchase_receipt_control import activate_purchase_trace, render_purchases_with_trace
from src.team_commission_control import render_team_commission_control


activate_purchase_trace()
activate_executive_dashboard()
for section, label in (
    ("commission_assignments", "Asignaciones de comisión"),
    ("business_goal_actions", "Acciones de metas"),
):
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = label
session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)

# Esta extensión solo reemplaza renderers funcionales. La taxonomía de navegación
# es canónica en top_navigation_app y no debe mutarse mientras app_shell se importa.
app_shell.FUNCTIONAL_MODULES["Metas del negocio"] = render_business_goals_plus
app_shell.FUNCTIONAL_MODULES["Compras"] = render_purchases_with_trace
app_shell.FUNCTIONAL_MODULES["Equipo y comisiones"] = render_team_commission_control
app_shell.FUNCTIONAL_MODULES["Catálogo y producción"] = render_safe_catalog
app_shell.FUNCTIONAL_MODULES["Mantenimiento del catálogo"] = render_catalog_maintenance
app_shell.FUNCTIONAL_MODULES["Reversos de producción"] = render_production_reversal
app_shell.FUNCTIONAL_MODULES["Control financiero detallado"] = render_financial_control


def run_app() -> None:
    app_shell.run_app()
