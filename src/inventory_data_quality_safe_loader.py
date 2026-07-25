"""Activa el diagnóstico seguro de datos maestros de Inventario."""
from src import app_shell
from src.inventory_data_quality_safe import render_inventory_data_quality


def activate_inventory_data_quality_safe() -> None:
    """Añade el diagnóstico después de la pantalla vigente sin reemplazar su lógica."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Inventario")
    if current_renderer is None:
        return

    def render_inventory_with_data_quality() -> None:
        current_renderer()
        render_inventory_data_quality()

    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_with_data_quality
