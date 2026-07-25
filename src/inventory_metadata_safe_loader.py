"""Activa la octava mejora segura de Inventario."""
from src import inventory_enterprise
from src.inventory_metadata_safe import render_inventory_stock_with_metadata_editor


def activate_inventory_metadata_safe() -> None:
    """Añade edición auditada de ubicación, lote y vencimiento."""
    inventory_enterprise._catalog = render_inventory_stock_with_metadata_editor
