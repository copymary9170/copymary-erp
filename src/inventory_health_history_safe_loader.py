"""Activa el historial persistente seguro de salud de Inventario."""
from src import app_shell
from src.inventory_health_history_safe import render_inventory_health_history


def activate_inventory_health_history_safe() -> None:
    """Añade el historial después de la pantalla vigente sin reemplazar su lógica."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Inventario")
    if current_renderer is None:
        return

    def render_inventory_with_health_history() -> None:
        current_renderer()
        render_inventory_health_history()

    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_with_health_history
