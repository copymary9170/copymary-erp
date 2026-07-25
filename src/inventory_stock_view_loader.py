"""Activa la primera mejora segura de Inventario."""
from src import inventory_enterprise
from src.inventory_stock_view import render_inventory_stock_table


def activate_inventory_stock_view() -> None:
    """Sustituye solo la tabla visual de existencias.

    No altera movimientos, reservas, conteos, costos ni datos guardados.
    """
    inventory_enterprise._catalog = render_inventory_stock_table
