"""Activa la segunda mejora segura de Inventario."""
from src import inventory_enterprise
from src.inventory_movements_safe import render_inventory_movements_safe


def activate_inventory_movements_safe() -> None:
    """Sustituye solo la vista de Movimientos.

    No migra datos, no cambia costos y no modifica Recepción, Reservas,
    Conteo físico ni Reposición.
    """
    inventory_enterprise._movements = render_inventory_movements_safe
