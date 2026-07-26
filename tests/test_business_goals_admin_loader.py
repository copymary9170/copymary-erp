from __future__ import annotations

from types import SimpleNamespace

from src import app_shell
from src.business_goals_admin_loader import (
    PAGE_NAME,
    activate_business_goals_admin,
    actor_from_current_user,
)


def test_actor_is_resolved_from_authenticated_user(monkeypatch):
    monkeypatch.setattr(
        "src.business_goals_admin_loader.auth.current_user",
        lambda: SimpleNamespace(
            user_id="USR-1",
            role_id="ROL-1",
            role_name="Administrador",
        ),
    )
    actor = actor_from_current_user()
    assert actor.user_id == "USR-1"
    assert actor.role_id == "ROL-1"
    assert actor.role_name == "Administrador"


def test_activation_registers_reserved_navigation_page(monkeypatch):
    original = app_shell.FUNCTIONAL_MODULES.get(PAGE_NAME)
    try:
        app_shell.FUNCTIONAL_MODULES.pop(PAGE_NAME, None)
        activate_business_goals_admin()
        assert PAGE_NAME in app_shell.FUNCTIONAL_MODULES
        assert callable(app_shell.FUNCTIONAL_MODULES[PAGE_NAME])
    finally:
        if original is None:
            app_shell.FUNCTIONAL_MODULES.pop(PAGE_NAME, None)
        else:
            app_shell.FUNCTIONAL_MODULES[PAGE_NAME] = original
