"""Extensión de navegación para metas y controles de catálogo."""

from src import app_shell
from src.business_goals import render_business_goals
from src.catalog_maintenance import render_catalog_maintenance
from src.production_reversal import render_production_reversal


app_shell.FUNCTIONAL_MODULES["Metas del negocio"] = render_business_goals
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
