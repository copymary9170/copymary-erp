"""Activa la cuarta mejora segura de Inventario."""
from src import inventory_enterprise
from src.inventory_counts_safe import render_inventory_counts_safe


def activate_inventory_counts_safe() -> None:
    """Sustituye únicamente la vista de conteo físico.

    El ajuste se aplica solo después de revisar y confirmar la diferencia.
    """
    inventory_enterprise._counts = render_inventory_counts_safe
