"""Activa la décima mejora segura de Inventario."""
from src import inventory_enterprise
from src.inventory_flow_consistency_safe import (
    configure_base_renderer,
    render_inventory_with_consistent_flow,
)


def activate_inventory_flow_consistency_safe() -> None:
    """Envuelve la pantalla vigente con una guía visual, sin tocar su lógica."""
    current_renderer = inventory_enterprise.render_inventory_enterprise
    configure_base_renderer(current_renderer)
    inventory_enterprise.render_inventory_enterprise = render_inventory_with_consistent_flow
