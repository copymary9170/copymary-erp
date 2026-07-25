"""Activa la tercera mejora segura de Inventario."""
from src import inventory_enterprise
from src.inventory_dashboard_safe import render_inventory_dashboard


def activate_inventory_dashboard_safe() -> None:
    """Sustituye únicamente el panel visual del Inventario.

    No altera existencias, costos, reservas, movimientos ni registros guardados.
    """
    inventory_enterprise._dashboard = render_inventory_dashboard
