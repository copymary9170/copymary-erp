"""Activa la auditoría unificada de Inventario."""
from src import app_shell
from src.inventory_audit_unified_safe import render_inventory_unified_audit


def activate_inventory_unified_audit_safe() -> None:
    """Añade la auditoría al final sin reemplazar la pantalla vigente."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Inventario")
    if current_renderer is None:
        return

    def render_inventory_with_unified_audit() -> None:
        current_renderer()
        render_inventory_unified_audit()

    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_with_unified_audit
