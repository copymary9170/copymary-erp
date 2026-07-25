"""Activa la quinta mejora segura de Inventario."""
from src import inventory_enterprise
from src.inventory_reservations_safe import render_inventory_reservations_safe


def activate_inventory_reservations_safe() -> None:
    """Sustituye únicamente la vista de Reservas."""
    inventory_enterprise._reservations = render_inventory_reservations_safe
