"""Activación segura del gestor administrativo de metas empresariales.

Registra la pantalla en el shell existente y resuelve el actor desde la sesión
autenticada. Mantiene la interfaz desacoplada de navegación y login.
"""
from __future__ import annotations

from src import app_shell, auth
from src.business_goals_admin_closure import render_business_goals_admin_with_closure
from src.business_goals_service import GoalActor

PAGE_NAME = "Metas del negocio"


def actor_from_current_user() -> GoalActor:
    user = auth.current_user()
    return GoalActor(
        user_id=str(user.user_id),
        role_id=str(user.role_id or ""),
        role_name=str(user.role_name or ""),
    )


def render_business_goals_for_current_user() -> None:
    render_business_goals_admin_with_closure(actor=actor_from_current_user())


def activate_business_goals_admin() -> None:
    """Registra la pantalla sin reemplazar ni modificar módulos operativos."""
    app_shell.FUNCTIONAL_MODULES[PAGE_NAME] = render_business_goals_for_current_user
