"""Activa la novena mejora segura de Inventario."""
from src import app_shell
from src.inventory_workspace_safe import render_inventory_workspace_safe


def activate_inventory_workspace_safe() -> None:
    """Sustituye solo la pantalla principal de Inventario y evita un menú duplicado."""
    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_workspace_safe
    app_shell.FUNCTIONAL_MODULES.pop("Inventario empresarial", None)
