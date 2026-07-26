"""Fachada KPI-aware para creación y edición de metas persistentes.

Mantiene compatibilidad con el servicio de Fase 6B y añade el contrato del
registro KPI antes de ejecutar escrituras.
"""
from __future__ import annotations

from typing import Any

from src.business_goals_kpi_contract import validate_kpi_target
from src.business_goals_repository import GoalCreate, get_goal
from src.business_goals_service import (
    GoalActor,
    GoalUpdate,
    create_business_goal,
    update_business_goal,
)


def create_validated_business_goal(data: GoalCreate, actor: GoalActor) -> dict[str, Any]:
    validated = validate_kpi_target(data.kpi_code, data.target_value, data.target_value_type)
    normalized = GoalCreate(
        kpi_code=data.kpi_code.strip(),
        name=data.name,
        target_value=validated.value,
        start_date=data.start_date,
        due_date=data.due_date,
        company_id=data.company_id,
        description=data.description,
        target_value_type=validated.value_type,
        period_type=data.period_type,
        scope_type=data.scope_type,
        scope_id=data.scope_id,
        status=data.status,
    )
    return create_business_goal(normalized, actor)


def update_validated_business_goal(goal_id: str, data: GoalUpdate, actor: GoalActor) -> dict[str, Any]:
    current = get_goal(goal_id)
    if not current:
        raise ValueError("La meta no existe.")
    validate_kpi_target(current["kpi_code"], data.target_value, data.target_value_type)
    return update_business_goal(goal_id, data, actor)
