"""Interfaz administrativa de metas empresariales para la Fase 6B.

La interfaz delega permisos, validaciones, persistencia, historial y transiciones
a las capas de servicio. No ejecuta SQL directo ni modifica módulos operativos.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from src.business_goals_repository import GoalCreate
from src.business_goals_service import (
    GoalActor,
    GoalPermissionError,
    GoalUpdate,
    assign_business_goal,
    change_goal_status,
    effective_goals_for_actor,
    goal_history_for_actor,
    has_goal_permission,
)
from src.business_goals_validated_service import (
    create_validated_business_goal,
    update_validated_business_goal,
)
from src.home_kpi_registry import KPI_DEFINITIONS, definitions_by_key

_STATUS_LABELS = {
    "draft": "Borrador",
    "active": "Activa",
    "paused": "Pausada",
    "completed": "Cumplida",
    "closed": "Cerrada",
    "archived": "Archivada",
}
_SCOPE_LABELS = {"company": "Empresa", "role": "Rol", "user": "Usuario"}
_VALUE_TYPE_BY_UNIT = {"currency": "currency", "percent": "percentage", "number": "number"}


def _date_text(value: Any, fallback: date | None = None) -> str:
    raw = str(value or "").strip()
    if raw:
        return raw[:10]
    return (fallback or date.today()).isoformat()


def _goal_options(goals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        f"{goal['name']} · {_STATUS_LABELS.get(goal['status'], goal['status'])} · {goal['id']}": goal
        for goal in goals
    }


def _render_create(actor: GoalActor, company_id: str) -> None:
    if not has_goal_permission(actor, "create"):
        st.info("No tienes permiso para crear metas empresariales.")
        return

    definitions = definitions_by_key()
    labels = {definition.label: definition for definition in KPI_DEFINITIONS}
    with st.form("goal_admin_create", clear_on_submit=True):
        st.markdown("#### Nueva meta")
        left, right = st.columns(2)
        selected_label = left.selectbox("KPI", tuple(labels))
        definition = labels[selected_label]
        name = right.text_input("Nombre", value=definition.label)
        description = st.text_area("Descripción", value=definition.description)
        value_type = _VALUE_TYPE_BY_UNIT.get(definition.unit, "number")
        target = st.number_input("Valor objetivo", min_value=0.0, value=float(definition.target))
        period_type = st.selectbox("Periodo", ("monthly", "quarterly", "annual", "custom"), index=0)
        dates = st.columns(2)
        start_date = dates[0].date_input("Inicio", value=date.today())
        due_date = dates[1].date_input("Vencimiento", value=date.today())
        scope = st.selectbox("Alcance", ("company", "role", "user"), format_func=lambda item: _SCOPE_LABELS[item])
        scope_id = ""
        if scope == "role":
            scope_id = st.text_input("ID del rol", value=actor.role_id)
        elif scope == "user":
            scope_id = st.text_input("ID del usuario", value=actor.user_id)
        status = st.selectbox("Estado inicial", ("draft", "active"), format_func=lambda item: _STATUS_LABELS[item])
        submitted = st.form_submit_button("Crear meta", type="primary", use_container_width=True)

    if not submitted:
        return
    try:
        create_validated_business_goal(
            GoalCreate(
                company_id=company_id,
                kpi_code=definition.key,
                name=name,
                description=description,
                target_value=float(target),
                target_value_type=value_type,
                period_type=period_type,
                start_date=start_date.isoformat(),
                due_date=due_date.isoformat(),
                scope_type=scope,
                scope_id=scope_id,
                status=status,
            ),
            actor,
        )
    except (ValueError, GoalPermissionError) as exc:
        st.error(str(exc))
    else:
        st.success("Meta creada correctamente.")
        st.rerun()


def _render_edit(actor: GoalActor, goal: dict[str, Any]) -> None:
    if not has_goal_permission(actor, "edit"):
        st.info("No tienes permiso para editar metas.")
        return
    if goal["status"] in {"closed", "archived"}:
        st.info("Las metas cerradas o archivadas son de solo lectura.")
        return

    with st.form(f"goal_admin_edit::{goal['id']}"):
        st.markdown("#### Editar meta")
        name = st.text_input("Nombre", value=goal["name"])
        description = st.text_area("Descripción", value=goal.get("description", ""))
        target = st.number_input("Valor objetivo", min_value=0.0, value=float(goal["target_value"]))
        period_options = ("monthly", "quarterly", "annual", "custom")
        current_period = goal.get("period_type", "custom")
        period_type = st.selectbox("Periodo", period_options, index=period_options.index(current_period) if current_period in period_options else 3)
        dates = st.columns(2)
        start_date = dates[0].date_input("Inicio", value=date.fromisoformat(_date_text(goal.get("start_date"))))
        due_date = dates[1].date_input("Vencimiento", value=date.fromisoformat(_date_text(goal.get("due_date"))))
        scope_options = ("company", "role", "user")
        current_scope = goal.get("scope_type", "company")
        scope = st.selectbox("Alcance", scope_options, index=scope_options.index(current_scope), format_func=lambda item: _SCOPE_LABELS[item])
        scope_id = st.text_input("ID del alcance", value=goal.get("scope_id", ""), disabled=scope == "company")
        reason = st.text_input("Motivo del cambio")
        submitted = st.form_submit_button("Guardar cambios", type="primary", use_container_width=True)

    if not submitted:
        return
    try:
        update_validated_business_goal(
            goal["id"],
            GoalUpdate(
                name=name,
                description=description,
                target_value=float(target),
                target_value_type=goal["target_value_type"],
                period_type=period_type,
                start_date=start_date.isoformat(),
                due_date=due_date.isoformat(),
                scope_type=scope,
                scope_id="" if scope == "company" else scope_id,
                reason=reason,
            ),
            actor,
        )
    except (ValueError, GoalPermissionError) as exc:
        st.error(str(exc))
    else:
        st.success("Meta actualizada.")
        st.rerun()


def _render_assignment(actor: GoalActor, goal: dict[str, Any]) -> None:
    if not has_goal_permission(actor, "assign"):
        return
    with st.expander("Asignar responsabilidad"):
        assignee_type = st.selectbox("Tipo", ("user", "role"), key=f"assign_type::{goal['id']}")
        assignee_id = st.text_input("ID del responsable", key=f"assign_id::{goal['id']}")
        weight = st.number_input("Peso", min_value=0.01, value=1.0, key=f"assign_weight::{goal['id']}")
        if st.button("Asignar", key=f"assign_submit::{goal['id']}"):
            try:
                assign_business_goal(
                    goal_id=goal["id"], assignee_type=assignee_type,
                    assignee_id=assignee_id, actor=actor, weight=float(weight),
                )
            except (ValueError, GoalPermissionError) as exc:
                st.error(str(exc))
            else:
                st.success("Responsable asignado.")
                st.rerun()


def _render_status(actor: GoalActor, goal: dict[str, Any]) -> None:
    available = {
        "draft": ("active", "archived"),
        "active": ("paused", "completed", "closed", "archived"),
        "paused": ("active", "closed", "archived"),
        "completed": ("closed", "active", "archived"),
        "closed": ("active", "archived"),
        "archived": (),
    }.get(goal["status"], ())
    if not available:
        return
    with st.expander("Cambiar estado"):
        new_status = st.selectbox("Nuevo estado", available, format_func=lambda item: _STATUS_LABELS[item], key=f"status::{goal['id']}")
        reason = st.text_input("Motivo", key=f"status_reason::{goal['id']}")
        if st.button("Aplicar estado", key=f"status_submit::{goal['id']}"):
            try:
                change_goal_status(goal["id"], new_status, actor, reason)
            except (ValueError, GoalPermissionError) as exc:
                st.error(str(exc))
            else:
                st.success("Estado actualizado.")
                st.rerun()


def _render_history(actor: GoalActor, goal: dict[str, Any]) -> None:
    if not has_goal_permission(actor, "history_view"):
        return
    with st.expander("Historial y auditoría funcional"):
        try:
            rows = goal_history_for_actor(goal["id"], actor)
        except GoalPermissionError as exc:
            st.error(str(exc))
            return
        if not rows:
            st.caption("La meta todavía no tiene eventos de historial.")
            return
        st.dataframe(rows, use_container_width=True, hide_index=True)


def render_business_goals_admin(*, actor: GoalActor, company_id: str = "default") -> None:
    """Renderiza el gestor administrativo sin acoplarlo a navegación o login."""
    st.markdown("## Gestión de metas empresariales")
    st.caption("Metas persistentes, versionadas y sujetas a permisos. No modifica registros operativos.")
    try:
        goals = effective_goals_for_actor(company_id=company_id, actor=actor, include_inactive=True)
    except GoalPermissionError as exc:
        st.warning(str(exc))
        return

    create_tab, manage_tab = st.tabs(("Crear", "Administrar"))
    with create_tab:
        _render_create(actor, company_id)
    with manage_tab:
        if not goals:
            st.info("No existen metas aplicables para este usuario.")
            return
        options = _goal_options(goals)
        selected = st.selectbox("Meta", tuple(options))
        goal = options[selected]
        definition = definitions_by_key().get(goal["kpi_code"])
        st.markdown(f"### {goal['name']}")
        st.caption(
            f"KPI: {definition.label if definition else goal['kpi_code']} · "
            f"Estado: {_STATUS_LABELS.get(goal['status'], goal['status'])} · "
            f"Alcance: {_SCOPE_LABELS.get(goal['scope_type'], goal['scope_type'])} · "
            f"Versión: {goal['version']}"
        )
        metrics = st.columns(3)
        metrics[0].metric("Objetivo", f"{float(goal['target_value']):,.2f}")
        metrics[1].metric("Inicio", goal["start_date"])
        metrics[2].metric("Vencimiento", goal["due_date"])
        _render_edit(actor, goal)
        _render_assignment(actor, goal)
        _render_status(actor, goal)
        _render_history(actor, goal)
