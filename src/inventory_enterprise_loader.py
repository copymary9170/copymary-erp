"""Activa la versión empresarial del módulo Inventario."""
from src import app_shell
from src import inventory_enterprise as inventory_module


def activate_inventory_enterprise() -> None:
    app_shell.FUNCTIONAL_MODULES["Inventario"] = inventory_module.render_inventory_enterprise
    try:
        from src import top_navigation_app
        top_navigation_app.DESCRIPTIONS["Inventario"] = (
            "Control de existencias, costos, movimientos, conteos, lotes y reposición integrado con Producción."
        )
    except (ImportError, KeyError):
        pass
