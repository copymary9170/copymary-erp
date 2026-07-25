"""Activa las reglas seguras de consistencia de Inventario."""
from src import app_shell
from src.inventory_consistency_rules_safe import render_inventory_consistency_rules


def activate_inventory_consistency_rules_safe() -> None:
    """Añade el diagnóstico al final de la pantalla vigente."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Inventario")
    if current_renderer is None:
        return

    def render_inventory_with_consistency_rules() -> None:
        current_renderer()
        render_inventory_consistency_rules()

    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_with_consistency_rules
