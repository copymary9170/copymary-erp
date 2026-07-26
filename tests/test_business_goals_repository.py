from __future__ import annotations

import pytest

from src.business_goals_repository import (
    GoalCreate,
    add_progress_snapshot,
    assign_goal,
    create_goal,
    get_goal,
    list_effective_goals,
    list_goal_history,
    transition_goal,
)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("COPYMARY_DB_PATH", str(tmp_path / "goals.sqlite3"))
    monkeypatch.delenv("COPYMARY_DATABASE_URL", raising=False)


def _goal(**overrides) -> GoalCreate:
    values = {
        "kpi_code": "monthly_sales",
        "name": "Ventas del mes",
        "target_value": 1000,
        "start_date": "2026-07-01",
        "due_date": "2026-07-31",
        "status": "active",
    }
    values.update(overrides)
    return GoalCreate(**values)


def test_create_goal_persists_and_creates_history():
    created = create_goal(_goal(), "USR-ADMIN")

    stored = get_goal(created["id"])
    history = list_goal_history(created["id"])

    assert stored is not None
    assert stored["name"] == "Ventas del mes"
    assert stored["version"] == 1
    assert len(history) == 1
    assert history[0]["change_type"] == "created"


def test_effective_goals_resolve_company_role_and_user_without_duplicates():
    company = create_goal(_goal(name="Empresa"), "USR-ADMIN")
    role = create_goal(
        _goal(name="Rol", scope_type="role", scope_id="ROL-VENTAS"),
        "USR-ADMIN",
    )
    personal = create_goal(
        _goal(name="Personal", scope_type="user", scope_id="USR-ANA"),
        "USR-ADMIN",
    )
    assign_goal(role["id"], "user", "USR-ANA", "USR-ADMIN")

    effective = list_effective_goals(
        company_id="default",
        user_id="USR-ANA",
        role_ids=["ROL-VENTAS"],
    )

    assert {goal["id"] for goal in effective} == {
        company["id"],
        role["id"],
        personal["id"],
    }


def test_invalid_dates_are_rejected():
    with pytest.raises(ValueError, match="due_date"):
        create_goal(
            _goal(start_date="2026-08-01", due_date="2026-07-31"),
            "USR-ADMIN",
        )


def test_status_transition_is_versioned_and_audited_in_history():
    created = create_goal(_goal(), "USR-ADMIN")

    closed = transition_goal(created["id"], "closed", "USR-ADMIN", "Cierre mensual")
    history = list_goal_history(created["id"])

    assert closed["status"] == "closed"
    assert closed["version"] == 2
    assert closed["closed_by"] == "USR-ADMIN"
    assert history[-1]["change_type"] == "status_transition"
    assert history[-1]["reason"] == "Cierre mensual"


def test_archived_goal_cannot_transition():
    created = create_goal(_goal(status="draft"), "USR-ADMIN")
    transition_goal(created["id"], "archived", "USR-ADMIN")

    with pytest.raises(ValueError, match="Transición no permitida"):
        transition_goal(created["id"], "active", "USR-ADMIN")


def test_progress_snapshot_validates_period():
    created = create_goal(_goal(), "USR-ADMIN")

    with pytest.raises(ValueError, match="measurement_period_end"):
        add_progress_snapshot(
            goal_id=created["id"],
            measured_value=100,
            progress_percentage=10,
            calculated_status="En curso",
            measurement_period_start="2026-07-31",
            measurement_period_end="2026-07-01",
            calculation_source="test",
        )
