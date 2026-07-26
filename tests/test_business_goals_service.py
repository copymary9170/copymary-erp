from __future__ import annotations

import pytest

from src.business_goals_repository import GoalCreate, create_goal, get_goal, list_goal_history
from src.business_goals_service import (
    GoalActor,
    GoalPermissionError,
    GoalUpdate,
    close_goal_with_snapshot,
    has_goal_permission,
    update_business_goal,
)


ADMIN = GoalActor("USR-ADMIN", "ROL-ADMIN", "Administrador")
LIMITED = GoalActor("USR-LIMITED", "ROL-LIMITED", "Operador")


def _goal() -> GoalCreate:
    return GoalCreate(
        kpi_code="monthly_sales",
        name="Ventas mensuales",
        target_value=1000,
        target_value_type="currency",
        start_date="2026-07-01",
        due_date="2026-07-31",
        status="active",
    )


def test_admin_has_all_goal_permissions(monkeypatch):
    assert has_goal_permission(ADMIN, "view") is True
    assert has_goal_permission(ADMIN, "create") is True
    assert has_goal_permission(ADMIN, "history_view") is True
    assert has_goal_permission(ADMIN, "unknown") is False


def test_non_admin_is_deny_by_default(monkeypatch):
    class EmptyConnection:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("src.business_goals_service.ensure_goal_schema", lambda: None)
    monkeypatch.setattr("src.business_goals_service.connect", lambda: EmptyConnection())
    assert has_goal_permission(LIMITED, "edit") is False


def test_update_rejects_closed_goal(monkeypatch):
    monkeypatch.setattr("src.business_goals_service.require_goal_permission", lambda *_args: None)
    monkeypatch.setattr(
        "src.business_goals_service.get_goal",
        lambda _goal_id: {"id": "GOL-1", "status": "closed"},
    )
    with pytest.raises(ValueError, match="cerrada o archivada"):
        update_business_goal(
            "GOL-1",
            GoalUpdate(
                name="Nueva", description="", target_value=1,
                target_value_type="number", period_type="custom",
                start_date="2026-07-01", due_date="2026-07-31",
                scope_type="company",
            ),
            ADMIN,
        )


def test_formal_close_requires_reason(monkeypatch):
    monkeypatch.setattr("src.business_goals_service.require_goal_permission", lambda *_args: None)
    with pytest.raises(ValueError, match="requiere un motivo"):
        close_goal_with_snapshot(
            goal_id="GOL-1", actor=ADMIN, measured_value=50,
            progress_percentage=50, calculated_status="En riesgo",
            measurement_period_start="2026-07-01",
            measurement_period_end="2026-07-31",
            calculation_source="monthly_sales", reason="",
        )


def test_update_creates_versioned_history(tmp_path, monkeypatch):
    monkeypatch.setenv("COPYMARY_DB_PATH", str(tmp_path / "goals.sqlite3"))
    goal = create_goal(_goal(), ADMIN.user_id)
    updated = update_business_goal(
        goal["id"],
        GoalUpdate(
            name="Ventas julio", description="Meta revisada", target_value=1250,
            target_value_type="currency", period_type="monthly",
            start_date="2026-07-01", due_date="2026-07-31",
            scope_type="company", reason="Ajuste aprobado",
        ),
        ADMIN,
    )
    assert updated["version"] == 2
    assert updated["target_value"] == 1250
    history = list_goal_history(goal["id"])
    assert any(row["change_type"] == "field_update" for row in history)


def test_formal_close_returns_final_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("COPYMARY_DB_PATH", str(tmp_path / "goals.sqlite3"))
    goal = create_goal(_goal(), ADMIN.user_id)
    result = close_goal_with_snapshot(
        goal_id=goal["id"], actor=ADMIN, measured_value=1000,
        progress_percentage=100, calculated_status="Cumplido",
        measurement_period_start="2026-07-01",
        measurement_period_end="2026-07-31",
        calculation_source="monthly_sales", reason="Periodo finalizado",
    )
    assert result["status"] == "closed"
    assert result["final_snapshot_id"].startswith("GSS-")
    assert get_goal(goal["id"])["closed_by"] == ADMIN.user_id
