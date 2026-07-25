"""Activa la séptima mejora segura de Inventario."""
from src import inventory_enterprise
from src.inventory_lots_safe import render_inventory_stock_with_lots


def activate_inventory_lots_safe() -> None:
    """Extiende Existencias con lotes y vencimientos sin cambiar datos."""
    inventory_enterprise._catalog = render_inventory_stock_with_lots
