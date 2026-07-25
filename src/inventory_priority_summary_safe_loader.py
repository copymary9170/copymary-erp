"""Activa el resumen seguro de prioridades de Inventario."""
from src import app_shell
from src.inventory_priority_summary_safe import render_inventory_priority_summary


def activate_inventory_priority_summary_safe() -> None:
    """Añade el resumen después de la pantalla vigente sin reemplazar su lógica."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Inventario")
    if current_renderer is None:
        return

    def render_inventory_with_priority_summary() -> None:
        current_renderer()
        render_inventory_priority_summary()

    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_with_priority_summary
