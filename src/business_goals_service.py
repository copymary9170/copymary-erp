"""Servicio empresarial de metas para la Fase 6B.

Centraliza permisos, edición versionada y cierre formal para que la interfaz no
ejecute SQL ni decida transiciones por su cuenta.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable
from uuid import uuid4

from src.business_goals_repository import (
    GoalCreate,
    add_progress_snapshot,
    assign_goal,
    create_goal,
    ensure_goal_schema,
    get_goal,
    list_effective_goals,
    list_goal_history,
    transition_goal,
    validate_goal,
)
from src.erp_database import connect, record_audit_event
from src.session_utils import now_iso

GOAL_MODULE = "goals"
GOAL_ACTIONS = {"view", "create", "edit", "assign", "close", "history_view"}
ADMIN_ROLE_NAME = "Administrador"


class GoalPermissionError(PermissionError):
    pass


@dataclass(frozen=True)
class GoalActor:
    user_id: str
    role_id: str
    role_name: str


@dataclass(frozen=True)
class GoalUpdate:
    name: str
    description: str
    target_value: float
    target_value_type: str
    period_type: str
    start_date: str
    due_date: str
    scope_type: str
    scope_id: str = ""
    reason: str = ""


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12].upper()}"


def has_goal_permission(actor: GoalActor, action: str) -> bool:
    if action not in GOAL_ACTIONS:
        return False
    if actor.role_name == ADMIN_ROLE_NAME:
        return True
    if not actor.role_id:
        return False
    ensure_goal_schema()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT allowed FROM app_permissions
             WHERE role_id = ? AND module_name = ? AND action_name = ?
             LIMIT 1
            """,
            (actor.role_id, GOAL_MODULE, action),
        ).fetchone()
    return bool(row and row["allowed"])


def require_goal_permission(actor: GoalActor, action: str) -> None:
    if not actor.user_id:
        raise GoalPermissionError("Se requiere un usuario autenticado.")
    if not has_goal_permission(actor, action):
        raise GoalPermissionError(f"Permiso requerido: goal_{action}.")


def create_business_goal(data: GoalCreate, actor: GoalActor) -> dict[str, Any]:
    require_goal_permission(actor, "create")
    return create_goal(data, actor.user_id)


def effective_goals_for_actor(
    *, company_id: str, actor: GoalActor, extra_role_ids: Iterable[str] = (),
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    require_goal_permission(actor, "view")
    role_ids = tuple(dict.fromkeys((actor.role_id, *extra_role_ids)))
    return list_effective_goals(
        company_id=company_id,
        user_id=actor.user_id,
        role_ids=role_ids,
        include_inactive=include_inactive,
    )


def goal_history_for_actor(goal_id: str, actor: GoalActor) -> list[dict[str, Any]]:
    require_goal_permission(actor, "history_view")
    return list_goal_history(goal_id)


def assign_business_goal(
    *, goal_id: str, assignee_type: str, assignee_id: str,
    actor: GoalActor, weight: float = 1.0,
) -> str:
    require_goal_permission(actor, "assign")
    return assign_goal(goal_id, assignee_type, assignee_id, actor.user_id, weight)


def update_business_goal(goal_id: str, data: GoalUpdate, actor: GoalActor) -> dict[str, Any]:
    require_goal_permission(actor, "edit")
    before = get_goal(goal_id)
    if not before:
        raise ValueError("La meta no existe.")
    if before["status"] in {"closed", "archived"}:
        raise ValueError("Una meta cerrada o archivada no admite edición directa.")

    candidate = GoalCreate(
        company_id=before["company_id"], kpi_code=before["kpi_code"],
        name=data.name, description=data.description,
        target_value=data.target_value, target_value_type=data.target_value_type,
        period_type=data.period_type, start_date=data.start_date,
        due_date=data.due_date, scope_type=data.scope_type,
        scope_id=data.scope_id, status=before["status"],
    )
    validate_goal(candidate)

    editable = {
        "name": data.name.strip(), "description": data.description.strip(),
        "target_value": float(data.target_value),
        "target_value_type": data.target_value_type,
        "period_type": data.period_type, "start_date": data.start_date,
        "due_date": data.due_date, "scope_type": data.scope_type,
        "scope_id": data.scope_id.strip(),
    }
    changes = {key: value for key, value in editable.items() if before.get(key) != value}
    if not changes:
        return before

    timestamp = now_iso()
    next_version = int(before["version"]) + 1
    with connect() as connection:
        connection.execute(
            """
            UPDATE business_goals
               SET name = ?, description = ?, target_value = ?, target_value_type = ?,
                   period_type = ?, start_date = ?, due_date = ?, scope_type = ?,
                   scope_id = ?, version = ?, updated_by = ?, updated_at = ?
             WHERE id = ?
            """,
            (editable["name"], editable["description"], editable["target_value"],
             editable["target_value_type"], editable["period_type"], editable["start_date"],
             editable["due_date"], editable["scope_type"], editable["scope_id"],
             next_version, actor.user_id, timestamp, goal_id),
        )
        for field_name, new_value in changes.items():
            connection.execute(
                """
                INSERT INTO goal_history(
                    id, goal_id, goal_version, change_type, field_name,
                    previous_value, new_value, reason, changed_by, changed_at
                ) VALUES (?, ?, ?, 'field_update', ?, ?, ?, ?, ?, ?)
                """,
                (_new_id("GHI"), goal_id, next_version, field_name,
                 json.dumps(before.get(field_name), ensure_ascii=False),
                 json.dumps(new_value, ensure_ascii=False), data.reason.strip(),
                 actor.user_id, timestamp),
            )

    after = get_goal(goal_id) or {}
    record_audit_event(
        GOAL_MODULE, "business_goals", goal_id, "update",
        before=before, after=after, reason=data.reason,
        actor_user_id=actor.user_id,
    )
    return after


def change_goal_status(goal_id: str, new_status: str, actor: GoalActor, reason: str = "") -> dict[str, Any]:
    action = "close" if new_status in {"completed", "closed", "archived"} else "edit"
    require_goal_permission(actor, action)
    return transition_goal(goal_id, new_status, actor.user_id, reason)


def close_goal_with_snapshot(
    *, goal_id: str, actor: GoalActor, measured_value: float,
    progress_percentage: float, calculated_status: str,
    measurement_period_start: str, measurement_period_end: str,
    calculation_source: str, reason: str,
) -> dict[str, Any]:
    require_goal_permission(actor, "close")
    if not reason.strip():
        raise ValueError("El cierre formal requiere un motivo.")
    before = get_goal(goal_id)
    if not before:
        raise ValueError("La meta no existe.")
    if before["status"] == "closed":
        raise ValueError("La meta ya está cerrada.")

    snapshot_id = add_progress_snapshot(
        goal_id=goal_id, measured_value=measured_value,
        progress_percentage=progress_percentage, calculated_status=calculated_status,
        measurement_period_start=measurement_period_start,
        measurement_period_end=measurement_period_end,
        calculation_source=f"{calculation_source}:final",
    )
    after = transition_goal(goal_id, "closed", actor.user_id, reason)
    after["final_snapshot_id"] = snapshot_id
    return after
