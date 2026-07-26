from __future__ import annotations

from src.home_persistent_goals import default_targets, resolve_dashboard_goals


def test_defaults_when_user_has_no_view_permission(monkeypatch):
    from src.business_goals_service import GoalPermissionError

    def deny(**_kwargs):
        raise GoalPermissionError("Permiso requerido: goal_view.")

    monkeypatch.setattr("src.home_persistent_goals.effective_goals_for_actor", deny)
    result = resolve_dashboard_goals(
        user_id="USR-1", role_id="ROL-1", role_name="Operador"
    )
    assert result.targets == default_targets()
    assert result.source == "defaults"
    assert result.editable is False
    assert "goal_view" in result.message


def test_personal_goal_overrides_role_and_company(monkeypatch):
    rows = [
        {"id": "G1", "kpi_code": "monthly_sales", "target_value": 4000,
         "scope_type": "company", "version": 3, "updated_at": "2026-07-01"},
        {"id": "G2", "kpi_code": "monthly_sales", "target_value": 5000,
         "scope_type": "role", "version": 1, "updated_at": "2026-07-02"},
        {"id": "G3", "kpi_code": "monthly_sales", "target_value": 6000,
         "scope_type": "user", "version": 1, "updated_at": "2026-07-03"},
    ]
    monkeypatch.setattr(
        "src.home_persistent_goals.effective_goals_for_actor", lambda **_kwargs: rows
    )
    result = resolve_dashboard_goals(
        user_id="USR-1", role_id="ROL-1", role_name="Administrador"
    )
    assert result.targets["monthly_sales"] == 6000
    assert result.persistent_goals["monthly_sales"]["id"] == "G3"
    assert result.source == "persistent"


def test_newer_version_wins_within_same_scope(monkeypatch):
    rows = [
        {"id": "OLD", "kpi_code": "healthy_inventory", "target_value": 80,
         "scope_type": "role", "version": 1, "updated_at": "2026-07-01"},
        {"id": "NEW", "kpi_code": "healthy_inventory", "target_value": 90,
         "scope_type": "role", "version": 2, "updated_at": "2026-07-02"},
    ]
    monkeypatch.setattr(
        "src.home_persistent_goals.effective_goals_for_actor", lambda **_kwargs: rows
    )
    result = resolve_dashboard_goals(
        user_id="USR-1", role_id="ROL-1", role_name="Administrador"
    )
    assert result.targets["healthy_inventory"] == 90
    assert result.persistent_goals["healthy_inventory"]["id"] == "NEW"


def test_unknown_kpi_is_ignored(monkeypatch):
    monkeypatch.setattr(
        "src.home_persistent_goals.effective_goals_for_actor",
        lambda **_kwargs: [{"kpi_code": "unknown", "target_value": 10}],
    )
    result = resolve_dashboard_goals(
        user_id="USR-1", role_id="ROL-1", role_name="Administrador"
    )
    assert result.targets == default_targets()
    assert result.source == "defaults"
