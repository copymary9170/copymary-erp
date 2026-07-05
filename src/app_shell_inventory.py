"""Extensión de navegación para ajustes de inventario."""

from src import app_shell
from src.app_shell_payments import run_app as _run_base_app
from src.inventory_adjustments import render_inventory_adjustments


app_shell.FUNCTIONAL_MODULES["Ajustes de inventario"] = render_inventory_adjustments
app_shell.NAVIGATION_GROUPS["Productos e inventario"] = (
    "Catálogo y producción",
    "Mantenimiento del catálogo",
    "Reversos de producción",
    "Inventario",
    "Ajustes de inventario",
    "Movimientos de inventario",
    "Alertas de inventario",
    "Costeo",
    "Ajustar precios",
    "Exportar precios",
)


def run_app() -> None:
    _run_base_app()
