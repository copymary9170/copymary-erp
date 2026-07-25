"""Activa la preparación segura del historial persistente de Inventario."""
from src import app_shell
from src.inventory_health_history_readiness_safe import render_inventory_health_history_readiness


def activate_inventory_health_history_readiness_safe() -> None:
    """Añade la preparación después de la pantalla vigente sin reemplazar su lógica."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Inventario")
    if current_renderer is None:
        return

    def render_inventory_with_history_readiness() -> None:
        current_renderer()
        render_inventory_health_history_readiness()

    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_with_history_readiness
