"""Activa la comparación temporal segura de salud de Inventario."""
from src import app_shell
from src.inventory_health_trend_safe import render_inventory_health_trend


def activate_inventory_health_trend_safe() -> None:
    """Añade la comparación después de la pantalla vigente sin reemplazar lógica."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Inventario")
    if current_renderer is None:
        return

    def render_inventory_with_health_trend() -> None:
        current_renderer()
        render_inventory_health_trend()

    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_with_health_trend
