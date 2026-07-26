"""Puente de lectura entre Inicio fase 6A y las metas persistentes de fase 6B.

El dashboard consume este módulo en lugar de conocer SQL, permisos o herencia.
Cuando no existen metas persistentes aplicables, conserva los valores declarativos
predeterminados para mantener compatibilidad progresiva.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.business_goals_service import (
    GoalActor,
    GoalPermissionError,
    effective_goals_for_actor,
)
from src.home_kpi_registry import KPI_DEFINITIONS


@dataclass(frozen=True)
class DashboardGoalSet:
    targets: dict[str, float]
    persistent_goals: dict[str, dict[str, Any]]
    source: str
    editable: bool
    message: str = ""


def default_targets() -> dict[str, float]:
    return {definition.key: float(definition.target) for definition in KPI_DEFINITIONS}


def _goal_priority(goal: dict[str, Any]) -> tuple[int, int, str]:
    """Prioriza meta personal, luego rol y finalmente empresa; después versión."""
    scope_rank = {"user": 3, "role": 2, "company": 1}
    return (
        scope_rank.get(str(goal.get("scope_type", "company")), 0),
        int(goal.get("version") or 0),
        str(goal.get("updated_at") or goal.get("created_at") or ""),
    )


def resolve_dashboard_goals(
    *,
    user_id: str,
    role_id: str,
    role_name: str,
    company_id: str = "default",
) -> DashboardGoalSet:
    """Devuelve una meta efectiva por KPI sin duplicar registros persistentes.

    La ausencia de permiso de lectura no rompe Inicio: se muestran valores
    predeterminados y se informa que las metas persistentes no están disponibles.
    """
    defaults = default_targets()
    actor = GoalActor(user_id=user_id, role_id=role_id, role_name=role_name)
    try:
        rows = effective_goals_for_actor(company_id=company_id, actor=actor)
    except GoalPermissionError as exc:
        return DashboardGoalSet(
            targets=defaults,
            persistent_goals={},
            source="defaults",
            editable=False,
            message=str(exc),
        )

    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        kpi_code = str(row.get("kpi_code") or "").strip()
        if kpi_code not in defaults:
            continue
        current = selected.get(kpi_code)
        if current is None or _goal_priority(row) > _goal_priority(current):
            selected[kpi_code] = row

    targets = defaults.copy()
    for kpi_code, row in selected.items():
        try:
            targets[kpi_code] = max(float(row.get("target_value")), 0.0)
        except (TypeError, ValueError):
            continue

    return DashboardGoalSet(
        targets=targets,
        persistent_goals=selected,
        source="persistent" if selected else "defaults",
        editable=False,
        message="" if selected else "No existen metas persistentes aplicables; se usan valores predeterminados.",
    )
