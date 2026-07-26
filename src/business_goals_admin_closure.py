"""Extensión reversible del gestor de metas para cierre formal con snapshot final."""
from __future__ import annotations

from typing import Any

import streamlit as st

from src import business_goals_admin as admin
from src.business_goals_service import (
    GoalActor,
    GoalPermissionError,
    change_goal_status,
    close_goal_with_snapshot,
    has_goal_permission,
)


def calculate_progress(goal: dict[str, Any], measured_value: float) -> float:
    """Calcula cumplimiento según la dirección declarada del KPI."""
    definition = admin.definitions_by_key().get(str(goal.get("kpi_code") or ""))
    target = float(goal.get("target_value") or 0.0)
    measured = max(float(measured_value), 0.0)
    if not definition:
        return 0.0
    if definition.direction == "lower":
        if target <= 0:
            return 100.0 if measured <= 0 else 0.0
        if measured <= target:
            return 100.0
        return max(target / measured * 100.0, 0.0)
    if target <= 0:
        return 100.0 if measured >= 0 else 0.0
    return max(measured / target * 100.0, 0.0)


def calculated_status(progress_percentage: float) -> str:
    if progress_percentage >= 100:
        return "Cumplido"
    if progress_percentage >= 75:
        return "En curso"
    if progress_percentage >= 50:
        return "En riesgo"
    return "Crítico"


def render_status_with_formal_close(actor: GoalActor, goal: dict[str, Any]) -> None:
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
        new_status = st.selectbox(
            "Nuevo estado", available,
            format_func=lambda item: admin._STATUS_LABELS[item],
            key=f"status::{goal['id']}",
        )
        reason = st.text_input("Motivo", key=f"status_reason::{goal['id']}")

        if new_status == "closed":
            if not has_goal_permission(actor, "close"):
                st.info("No tienes permiso para cerrar metas.")
                return
            measured = st.number_input(
                "Valor final medido", min_value=0.0,
                value=float(goal.get("target_value") or 0.0),
                key=f"close_measured::{goal['id']}",
            )
            period = st.columns(2)
            start = period[0].date_input(
                "Inicio de medición",
                value=admin.date.fromisoformat(admin._date_text(goal.get("start_date"))),
                key=f"close_start::{goal['id']}",
            )
            end = period[1].date_input(
                "Fin de medición",
                value=admin.date.fromisoformat(admin._date_text(goal.get("due_date"))),
                key=f"close_end::{goal['id']}",
            )
            progress = calculate_progress(goal, float(measured))
            status = calculated_status(progress)
            st.caption(f"Cumplimiento final calculado: {progress:.1f}% · {status}")
            confirmed = st.checkbox(
                "Confirmo el cierre definitivo y la creación del snapshot final.",
                key=f"close_confirm::{goal['id']}",
            )
            if st.button("Cerrar meta formalmente", type="primary", key=f"close_submit::{goal['id']}"):
                if not confirmed:
                    st.error("Debes confirmar el cierre definitivo.")
                    return
                try:
                    result = close_goal_with_snapshot(
                        goal_id=goal["id"], actor=actor,
                        measured_value=float(measured),
                        progress_percentage=progress,
                        calculated_status=status,
                        measurement_period_start=start.isoformat(),
                        measurement_period_end=end.isoformat(),
                        calculation_source=str(goal.get("kpi_code") or "manual"),
                        reason=reason,
                    )
                except (ValueError, GoalPermissionError) as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Meta cerrada. Snapshot final: {result['final_snapshot_id']}")
                    st.rerun()
            return

        if st.button("Aplicar estado", key=f"status_submit::{goal['id']}"):
            try:
                change_goal_status(goal["id"], new_status, actor, reason)
            except (ValueError, GoalPermissionError) as exc:
                st.error(str(exc))
            else:
                st.success("Estado actualizado.")
                st.rerun()


def render_business_goals_admin_with_closure(*, actor: GoalActor, company_id: str = "default") -> None:
    """Activa el cierre formal solo durante el render de esta pantalla."""
    original = admin._render_status
    admin._render_status = render_status_with_formal_close
    try:
        admin.render_business_goals_admin(actor=actor, company_id=company_id)
    finally:
        admin._render_status = original
