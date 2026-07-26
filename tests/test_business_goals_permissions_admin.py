from __future__ import annotations

import pytest

from src.business_goals_permissions_admin import save_goal_permissions
from src.business_goals_service import GoalActor

ADMIN = GoalActor("USR-ADMIN", "ROL-ADMIN", "Administrador")
OPERATOR = GoalActor("USR-1", "ROL-1", "Operador")


def test_non_admin_cannot_configure_permissions():
    with pytest.raises(PermissionError, match="Administrador"):
        save_goal_permissions("ROL-VENTAS", {"view": True}, OPERATOR)


def test_role_id_is_required():
    with pytest.raises(ValueError, match="obligatorio"):
        save_goal_permissions("", {"view": True}, ADMIN)


def test_permissions_are_normalized_to_known_actions(monkeypatch):
    captured = []

    class FakeResult:
        def fetchall(self):
            return []

    class FakeConnection:
        def execute(self, sql, params=()):
            captured.append((sql, params))
            return FakeResult()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("src.business_goals_permissions_admin.initialize_database", lambda: None)
    monkeypatch.setattr("src.business_goals_permissions_admin.connect", lambda: FakeConnection())
    monkeypatch.setattr("src.business_goals_permissions_admin.record_audit_event", lambda *_args, **_kwargs: "AUD-1")

    save_goal_permissions("ROL-VENTAS", {"view": True, "unknown": True}, ADMIN)

    inserted = [params for sql, params in captured if sql.startswith("INSERT INTO app_permissions")]
    assert inserted
    assert all(params[1] == "goals" for params in inserted)
    assert any(params[2] == "view" and params[3] == 1 for params in inserted)
    assert all(params[2] != "unknown" for params in inserted)
