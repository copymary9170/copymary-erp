from __future__ import annotations

from src.home_dashboard_phase6 import _resolve_goal_set, _scope_label
from src.home_persistent_goals import DashboardGoalSet


def test_scope_labels_are_explicit():
    assert _scope_label(None) == "Valor predeterminado"
    assert _scope_label({"scope_type": "user"}) == "Meta personal"
    assert _scope_label({"scope_type": "role"}) == "Meta heredada por rol"
    assert _scope_label({"scope_type": "company"}) == "Meta de empresa"


def test_resolve_uses_authenticated_user(monkeypatch):
    class User:
        user_id = "USR-1"
        role_id = "ROL-1"
        role_name = "Administrador"

    captured = {}

    def fake_resolver(**kwargs):
        captured.update(kwargs)
        return DashboardGoalSet({}, {}, "defaults", False)

    monkeypatch.setattr("src.home_dashboard_phase6.current_user", lambda: User())
    monkeypatch.setattr("src.home_dashboard_phase6.resolve_dashboard_goals", fake_resolver)

    _resolve_goal_set("IGNORED")

    assert captured == {
        "user_id": "USR-1",
        "role_id": "ROL-1",
        "role_name": "Administrador",
    }


def test_resolve_falls_back_without_authenticated_user(monkeypatch):
    captured = {}

    def fake_resolver(**kwargs):
        captured.update(kwargs)
        return DashboardGoalSet({}, {}, "defaults", False)

    monkeypatch.setattr("src.home_dashboard_phase6.current_user", lambda: None)
    monkeypatch.setattr("src.home_dashboard_phase6.resolve_dashboard_goals", fake_resolver)

    _resolve_goal_set("USR-FALLBACK")

    assert captured == {
        "user_id": "USR-FALLBACK",
        "role_id": "",
        "role_name": "Sin rol",
    }
