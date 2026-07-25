"""Activa el plan seguro de revisión de Inventario."""
from src import app_shell
from src.inventory_review_plan_safe import render_inventory_review_plan


def activate_inventory_review_plan_safe() -> None:
    """Añade el plan después de la pantalla vigente sin reemplazar su lógica."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Inventario")
    if current_renderer is None:
        return

    def render_inventory_with_review_plan() -> None:
        current_renderer()
        render_inventory_review_plan()

    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_with_review_plan
