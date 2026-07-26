"""Persistencia transaccional de metas empresariales para la Fase 6B.

Este módulo es deliberadamente independiente de la interfaz Streamlit. Centraliza
el esquema, las validaciones básicas y las operaciones de lectura/escritura para
que el dashboard y el futuro gestor de metas no ejecuten SQL directo.

La creación del esquema es idempotente y compatible con SQLite y PostgreSQL a
través del adaptador existente de ``src.erp_database``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from typing import Any, Iterable
from uuid import uuid4

from src.erp_database import connect, initialize_database, record_audit_event
from src.session_utils import now_iso

GOAL_STATUSES = {"draft", "active", "paused", "completed", "closed", "archived"}
GOAL_SCOPES = {"company", "role", "user"}
ASSIGNEE_TYPES = {"user", "role"}

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active", "archived"},
    "active": {"paused", "completed", "closed", "archived"},
    "paused": {"active", "closed", "archived"},
    "completed": {"closed", "active", "archived"},
    "closed": {"active", "archived"},
    "archived": set(),
}


@dataclass(frozen=True)
class GoalCreate:
    kpi_code: str
    name: str
    target_value: float
    start_date: str
    due_date: str
    company_id: str = "default"
    description: str = ""
    target_value_type: str = "number"
    period_type: str = "custom"
    scope_type: str = "company"
    scope_id: str = ""
    status: str = "draft"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12].upper()}"


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} debe usar formato AAAA-MM-DD.") from exc


def validate_goal(data: GoalCreate) -> None:
    if not data.kpi_code.strip():
        raise ValueError("kpi_code es obligatorio.")
    if not data.name.strip():
        raise ValueError("name es obligatorio.")
    if data.status not in GOAL_STATUSES:
        raise ValueError(f"Estado inválido: {data.status}.")
    if data.scope_type not in GOAL_SCOPES:
        raise ValueError(f"Alcance inválido: {data.scope_type}.")
    if data.scope_type in {"role", "user"} and not data.scope_id.strip():
        raise ValueError("scope_id es obligatorio para metas de rol o usuario.")
    if data.target_value_type in {"number", "currency", "percentage"} and data.target_value < 0:
        raise ValueError("target_value no puede ser negativo.")
    if data.target_value_type == "percentage" and data.target_value > 100:
        raise ValueError("Una meta porcentual no puede superar 100.")
    start = _parse_date(data.start_date, "start_date")
    due = _parse_date(data.due_date, "due_date")
    if due < start:
        raise ValueError("due_date no puede ser anterior a start_date.")


def ensure_goal_schema() -> None:
    """Crea las cuatro tablas de la Fase 6B e índices no destructivos."""
    initialize_database()
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS business_goals (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL DEFAULT 'default',
                kpi_code TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                target_value REAL NOT NULL,
                target_value_type TEXT NOT NULL DEFAULT 'number',
                period_type TEXT NOT NULL DEFAULT 'custom',
                start_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                scope_type TEXT NOT NULL DEFAULT 'company',
                scope_id TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                closed_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT,
                archived_at TEXT
            );

            CREATE TABLE IF NOT EXISTS goal_assignments (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                assignee_type TEXT NOT NULL,
                assignee_id TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active',
                assigned_by TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                UNIQUE(goal_id, assignee_type, assignee_id)
            );

            CREATE TABLE IF NOT EXISTS goal_history (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                goal_version INTEGER NOT NULL,
                change_type TEXT NOT NULL,
                field_name TEXT NOT NULL DEFAULT '',
                previous_value TEXT,
                new_value TEXT,
                reason TEXT NOT NULL DEFAULT '',
                changed_by TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS goal_progress_snapshots (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                measured_value REAL NOT NULL,
                progress_percentage REAL NOT NULL,
                calculated_status TEXT NOT NULL,
                measurement_period_start TEXT NOT NULL,
                measurement_period_end TEXT NOT NULL,
                measured_at TEXT NOT NULL,
                calculation_source TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_business_goals_scope
                ON business_goals(company_id, scope_type, scope_id, status);
            CREATE INDEX IF NOT EXISTS idx_business_goals_due
                ON business_goals(due_date, status);
            CREATE INDEX IF NOT EXISTS idx_goal_assignments_goal
                ON goal_assignments(goal_id, assignee_type, assignee_id);
            CREATE INDEX IF NOT EXISTS idx_goal_history_goal
                ON goal_history(goal_id, changed_at);
            CREATE INDEX IF NOT EXISTS idx_goal_snapshots_goal
                ON goal_progress_snapshots(goal_id, measured_at);
            """
        )


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def create_goal(data: GoalCreate, actor_user_id: str) -> dict[str, Any]:
    validate_goal(data)
    ensure_goal_schema()
    actor = actor_user_id.strip()
    if not actor:
        raise ValueError("actor_user_id es obligatorio.")
    goal_id = _new_id("GOL")
    timestamp = now_iso()
    after = {
        "id": goal_id,
        "company_id": data.company_id,
        "kpi_code": data.kpi_code.strip(),
        "name": data.name.strip(),
        "description": data.description.strip(),
        "target_value": float(data.target_value),
        "target_value_type": data.target_value_type,
        "period_type": data.period_type,
        "start_date": data.start_date,
        "due_date": data.due_date,
        "status": data.status,
        "scope_type": data.scope_type,
        "scope_id": data.scope_id.strip(),
        "version": 1,
        "created_by": actor,
        "updated_by": actor,
        "closed_by": "",
        "created_at": timestamp,
        "updated_at": timestamp,
        "closed_at": None,
        "archived_at": None,
    }
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO business_goals(
                id, company_id, kpi_code, name, description, target_value,
                target_value_type, period_type, start_date, due_date, status,
                scope_type, scope_id, version, created_by, updated_by,
                closed_by, created_at, updated_at, closed_at, archived_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(after.values()),
        )
        connection.execute(
            """
            INSERT INTO goal_history(
                id, goal_id, goal_version, change_type, field_name,
                previous_value, new_value, reason, changed_by, changed_at
            ) VALUES (?, ?, 1, 'created', '', NULL, ?, '', ?, ?)
            """,
            (_new_id("GHI"), goal_id, json.dumps(after, ensure_ascii=False, sort_keys=True), actor, timestamp),
        )
    record_audit_event("goals", "business_goals", goal_id, "create", after=after, actor_user_id=actor)
    return after


def get_goal(goal_id: str) -> dict[str, Any] | None:
    ensure_goal_schema()
    with connect() as connection:
        row = connection.execute("SELECT * FROM business_goals WHERE id = ?", (goal_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_effective_goals(
    *,
    company_id: str,
    user_id: str,
    role_ids: Iterable[str] = (),
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    """Resuelve empresa + roles + usuario sin materializar copias por usuario."""
    ensure_goal_schema()
    statuses = GOAL_STATUSES if include_inactive else {"active", "paused", "completed"}
    role_ids = tuple(dict.fromkeys(role_id for role_id in role_ids if role_id))
    placeholders = ",".join("?" for _ in role_ids) or "NULL"
    query = f"""
        SELECT DISTINCT g.*
        FROM business_goals g
        LEFT JOIN goal_assignments a ON a.goal_id = g.id AND a.status = 'active'
        WHERE g.company_id = ?
          AND g.status IN ({','.join('?' for _ in statuses)})
          AND (
                g.scope_type = 'company'
             OR (g.scope_type = 'user' AND g.scope_id = ?)
             OR (g.scope_type = 'role' AND g.scope_id IN ({placeholders}))
             OR (a.assignee_type = 'user' AND a.assignee_id = ?)
             OR (a.assignee_type = 'role' AND a.assignee_id IN ({placeholders}))
          )
        ORDER BY g.due_date, g.name
    """
    params: list[Any] = [company_id, *sorted(statuses), user_id, *role_ids, user_id, *role_ids]
    with connect() as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    return [_row_to_dict(row) for row in rows]


def assign_goal(
    goal_id: str,
    assignee_type: str,
    assignee_id: str,
    actor_user_id: str,
    weight: float = 1.0,
) -> str:
    ensure_goal_schema()
    if assignee_type not in ASSIGNEE_TYPES:
        raise ValueError(f"Tipo de responsable inválido: {assignee_type}.")
    if not assignee_id.strip():
        raise ValueError("assignee_id es obligatorio.")
    if weight <= 0:
        raise ValueError("weight debe ser mayor que cero.")
    goal = get_goal(goal_id)
    if not goal:
        raise ValueError("La meta no existe.")
    assignment_id = _new_id("GAS")
    timestamp = now_iso()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO goal_assignments(
                id, goal_id, assignee_type, assignee_id, weight,
                status, assigned_by, assigned_at
            ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            ON CONFLICT(goal_id, assignee_type, assignee_id)
            DO UPDATE SET weight = excluded.weight, status = 'active',
                          assigned_by = excluded.assigned_by, assigned_at = excluded.assigned_at
            """,
            (assignment_id, goal_id, assignee_type, assignee_id.strip(), float(weight), actor_user_id, timestamp),
        )
    record_audit_event(
        "goals",
        "goal_assignments",
        assignment_id,
        "assign",
        after={"goal_id": goal_id, "assignee_type": assignee_type, "assignee_id": assignee_id, "weight": weight},
        actor_user_id=actor_user_id,
    )
    return assignment_id


def transition_goal(goal_id: str, new_status: str, actor_user_id: str, reason: str = "") -> dict[str, Any]:
    ensure_goal_schema()
    if new_status not in GOAL_STATUSES:
        raise ValueError(f"Estado inválido: {new_status}.")
    before = get_goal(goal_id)
    if not before:
        raise ValueError("La meta no existe.")
    current = before["status"]
    if new_status not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Transición no permitida: {current} → {new_status}.")
    timestamp = now_iso()
    next_version = int(before["version"]) + 1
    closed_at = timestamp if new_status == "closed" else before.get("closed_at")
    closed_by = actor_user_id if new_status == "closed" else before.get("closed_by", "")
    archived_at = timestamp if new_status == "archived" else before.get("archived_at")
    with connect() as connection:
        connection.execute(
            """
            UPDATE business_goals
               SET status = ?, version = ?, updated_by = ?, updated_at = ?,
                   closed_by = ?, closed_at = ?, archived_at = ?
             WHERE id = ?
            """,
            (new_status, next_version, actor_user_id, timestamp, closed_by, closed_at, archived_at, goal_id),
        )
        connection.execute(
            """
            INSERT INTO goal_history(
                id, goal_id, goal_version, change_type, field_name,
                previous_value, new_value, reason, changed_by, changed_at
            ) VALUES (?, ?, ?, 'status_transition', 'status', ?, ?, ?, ?, ?)
            """,
            (_new_id("GHI"), goal_id, next_version, current, new_status, reason, actor_user_id, timestamp),
        )
    after = get_goal(goal_id) or {}
    record_audit_event(
        "goals", "business_goals", goal_id, "status_transition",
        before=before, after=after, reason=reason, actor_user_id=actor_user_id,
    )
    return after


def add_progress_snapshot(
    *,
    goal_id: str,
    measured_value: float,
    progress_percentage: float,
    calculated_status: str,
    measurement_period_start: str,
    measurement_period_end: str,
    calculation_source: str,
) -> str:
    ensure_goal_schema()
    if not get_goal(goal_id):
        raise ValueError("La meta no existe.")
    start = _parse_date(measurement_period_start, "measurement_period_start")
    end = _parse_date(measurement_period_end, "measurement_period_end")
    if end < start:
        raise ValueError("measurement_period_end no puede ser anterior al inicio.")
    snapshot_id = _new_id("GSS")
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO goal_progress_snapshots(
                id, goal_id, measured_value, progress_percentage,
                calculated_status, measurement_period_start,
                measurement_period_end, measured_at, calculation_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id, goal_id, float(measured_value), float(progress_percentage),
                calculated_status, measurement_period_start, measurement_period_end,
                now_iso(), calculation_source,
            ),
        )
    return snapshot_id


def list_goal_history(goal_id: str) -> list[dict[str, Any]]:
    ensure_goal_schema()
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM goal_history WHERE goal_id = ? ORDER BY changed_at, id",
            (goal_id,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]
