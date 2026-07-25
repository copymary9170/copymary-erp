"""Permisos granulares para operaciones sensibles de Inventario.

El rol Administrador conserva acceso total. Los demás roles necesitan una fila
explícita en ``app_permissions`` para el módulo ``Inventario`` y la acción
solicitada. La ausencia de permiso siempre deniega la operación.
"""
from __future__ import annotations

from src.auth import ADMIN_ROLE_NAME, current_user, permissions_for_role

MODULE_NAME = "Inventario"

ACTION_LABELS = {
    "count_adjustment_apply": "Aplicar ajustes por conteo físico",
    "reservation_create": "Crear reservas",
    "reservation_release": "Liberar reservas",
    "reservation_consume": "Consumir reservas",
    "metadata_edit": "Editar ubicación, lote y vencimiento",
    "cost_view": "Visualizar costos de inventario",
}


def can_inventory_action(action_name: str) -> bool:
    """Comprueba un permiso de acción con denegación por defecto."""
    user = current_user()
    if user is None:
        return False
    if user.role_name == ADMIN_ROLE_NAME:
        return True
    return any(
        row.get("module_name") == MODULE_NAME
        and row.get("action_name") == action_name
        and bool(row.get("allowed"))
        for row in permissions_for_role(user.role_id)
    )


def require_inventory_action(action_name: str) -> None:
    """Impide ejecutar una escritura aunque la interfaz haya sido manipulada."""
    if not can_inventory_action(action_name):
        label = ACTION_LABELS.get(action_name, action_name)
        raise PermissionError(f"No tienes permiso para: {label}.")
