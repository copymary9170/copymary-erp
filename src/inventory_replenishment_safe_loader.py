"""Activa la sexta mejora segura de Inventario."""
from src import inventory_enterprise
from src.inventory_replenishment_safe import render_inventory_replenishment_safe


def activate_inventory_replenishment_safe() -> None:
    """Sustituye solo la vista de Reposición.

    No crea órdenes, no modifica compras y no altera existencias.
    """
    inventory_enterprise._replenishment = render_inventory_replenishment_safe
