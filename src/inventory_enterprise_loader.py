"""Activa la versión empresarial del módulo Inventario."""
from src import app_shell
from src import inventory_enterprise as inventory_module


def _install_initial_stock_guard() -> None:
    original = inventory_module._movement
    if getattr(original, "_initial_stock_guard", False):
        return

    def guarded(item: dict, movement_type: str, quantity: float, reason: str, unit_cost: float = 0.0) -> None:
        if movement_type == "Entrada" and reason == "Existencia inicial":
            item["available_quantity"] = 0.0
        original(item, movement_type, quantity, reason, unit_cost)

    guarded._initial_stock_guard = True
    inventory_module._movement = guarded


def activate_inventory_enterprise() -> None:
    _install_initial_stock_guard()
    app_shell.FUNCTIONAL_MODULES["Inventario"] = inventory_module.render_inventory_enterprise
    try:
        from src import top_navigation_app
        top_navigation_app.DESCRIPTIONS["Inventario"] = (
            "Control de existencias, costos, movimientos, conteos, lotes y reposición integrado con Producción."
        )
    except (ImportError, KeyError):
        pass
