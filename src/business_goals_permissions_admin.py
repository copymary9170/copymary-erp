"""Administración explícita de permisos para metas empresariales.

Mantiene denegación por defecto y permite que un Administrador configure acciones
para un rol concreto sin alterar permisos de otros módulos.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from src.business_goals_service import ADMIN_ROLE_NAME, GOAL_ACTIONS, GOAL_MODULE, GoalActor
from src.erp_database import connect, initialize_database, record_audit_event

_ACTION_LABELS = {
    "view": "Ver metas",
    "create": "Crear metas",
    "edit": "Editar metas",
    "assign": "Asignar responsables",
    "close": "Cerrar o archivar",
    "history_view": "Ver historial",
}


def read_goal_permissions(role_id: str) -> dict[str, bool]:
    role = role_id.strip()
    if not role:
        return {action: False for action in GOAL_ACTIONS}
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            "SELECT action_name, allowed FROM app_permissions WHERE role_id = ? AND module_name = ?",
            (role, GOAL_MODULE),
        ).fetchall()
    stored = {str(row["action_name"]): bool(row["allowed"]) for row in rows}
    return {action: stored.get(action, False) for action in GOAL_ACTIONS}


def save_goal_permissions(role_id: str, permissions: dict[str, bool], actor: GoalActor) -> None:
    if actor.role_name != ADMIN_ROLE_NAME:
        raise PermissionError("Solo un Administrador puede configurar permisos de metas.")
    role = role_id.strip()
    if not role:
        raise ValueError("El ID del rol es obligatorio.")
    normalized = {action: bool(permissions.get(action, False)) for action in GOAL_ACTIONS}
    before = read_goal_permissions(role)
    initialize_database()
    with connect() as connection:
        for action, allowed in normalized.items():
            connection.execute(
                "DELETE FROM app_permissions WHERE role_id = ? AND module_name = ? AND action_name = ?",
                (role, GOAL_MODULE, action),
            )
            connection.execute(
                "INSERT INTO app_permissions(role_id, module_name, action_name, allowed) VALUES (?, ?, ?, ?)",
                (role, GOAL_MODULE, action, int(allowed)),
            )
    record_audit_event(
        GOAL_MODULE,
        "app_permissions",
        role,
        "configure_goal_permissions",
        before=before,
        after=normalized,
        reason="Configuración administrativa de permisos de metas",
        actor_user_id=actor.user_id,
    )


def render_goal_permissions_admin(actor: GoalActor) -> None:
    if actor.role_name != ADMIN_ROLE_NAME:
        return
    with st.expander("Permisos de metas por rol", expanded=False):
        st.caption("Los roles no configurados permanecen sin acceso. El Administrador conserva acceso total por diseño.")
        role_id = st.text_input("ID del rol", key="goal_permissions_role_id")
        current = read_goal_permissions(role_id) if role_id.strip() else {action: False for action in GOAL_ACTIONS}
        selected: dict[str, bool] = {}
        columns = st.columns(2)
        for index, action in enumerate(sorted(GOAL_ACTIONS)):
            selected[action] = columns[index % 2].checkbox(
                _ACTION_LABELS.get(action, action),
                value=current[action],
                key=f"goal_permission::{role_id}::{action}",
            )
        confirm = st.checkbox("Confirmo que deseo reemplazar los permisos de metas de este rol.", key="goal_permissions_confirm")
        if st.button("Guardar permisos", type="primary", disabled=not confirm, key="goal_permissions_save"):
            try:
                save_goal_permissions(role_id, selected, actor)
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            else:
                st.success("Permisos de metas actualizados.")
                st.rerun()
