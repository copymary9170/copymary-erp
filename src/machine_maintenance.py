"""Mantenimiento preventivo de máquinas para CopyMary ERP.

Cuarto y último gap de la revisión de negocio (dueña + finanzas +
producción): `production_machines` ya existe (para costeo, ver
bom_costing.py), con costo de depreciación por hora — pero no hay
calendario de mantenimiento ni alerta de máquina atrasada. Para un taller
con sublimadora/plotter/impresoras, una máquina sin mantenimiento
preventivo falla en el peor momento (un pedido grande) y sale más caro que
el mantenimiento mismo.

Alcance: planes de mantenimiento por máquina (tarea + frecuencia en días),
con próxima fecha calculada automáticamente, y bitácora de mantenimientos
realizados con su costo. No reemplaza el manual del fabricante de cada
máquina — la frecuencia recomendada debe salir de ahí, este módulo solo
ayuda a no perderla de vista.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database, record_audit_event
from src.money import format_money

TASK_SUGGESTIONS = ("Limpieza de cabezales", "Cambio de cuchilla", "Lubricación", "Calibración", "Revisión eléctrica", "Otro")


# ---------------------------------------------------------------------------
# Cálculo puro (testeable sin base de datos)
# ---------------------------------------------------------------------------

def days_until_due(plan: dict, as_of: date) -> int:
    """Días hasta el vencimiento. Negativo si ya está atrasado."""
    due_date = date.fromisoformat(str(plan["next_due_date"]))
    return (due_date - as_of).days


def is_overdue(plan: dict, as_of: date) -> bool:
    return days_until_due(plan, as_of) < 0


def is_due_soon(plan: dict, as_of: date, within_days: int = 7) -> bool:
    remaining = days_until_due(plan, as_of)
    return 0 <= remaining <= within_days


def overdue_plans(plans: list[dict], as_of: date) -> list[dict]:
    return [plan for plan in plans if plan.get("active") and is_overdue(plan, as_of)]


def due_soon_plans(plans: list[dict], as_of: date, within_days: int = 7) -> list[dict]:
    return [plan for plan in plans if plan.get("active") and is_due_soon(plan, as_of, within_days)]


def next_due_date_after(performed_date: date, frequency_days: int) -> date:
    return performed_date + timedelta(days=frequency_days)


# ---------------------------------------------------------------------------
# Acceso a datos
# ---------------------------------------------------------------------------

def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def list_machines() -> list[dict]:
    return _fetch_all("SELECT * FROM production_machines WHERE active = 1 ORDER BY name")


def list_plans() -> list[dict]:
    return _fetch_all(
        """
        SELECT mp.*, m.name AS machine_name
        FROM maintenance_plans mp JOIN production_machines m ON m.machine_id = mp.machine_id
        ORDER BY mp.next_due_date
        """
    )


def create_plan(machine_id: str, task_name: str, frequency_days: int, notes: str = "") -> str:
    initialize_database()
    plan_id = f"MNT-{uuid4().hex[:8].upper()}"
    next_due = next_due_date_after(date.today(), frequency_days).isoformat()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO maintenance_plans(plan_id, machine_id, task_name, frequency_days, last_done_date, next_due_date, notes, active, created_at_utc)
            VALUES (?, ?, ?, ?, NULL, ?, ?, 1, ?)
            """,
            (plan_id, machine_id, task_name.strip(), frequency_days, next_due, notes.strip(), date.today().isoformat()),
        )
    return plan_id


def logs_for_plan(plan_id: str) -> list[dict]:
    return _fetch_all("SELECT * FROM maintenance_logs WHERE plan_id = ? ORDER BY performed_date DESC", (plan_id,))


def register_maintenance(plan_id: str, machine_id: str, performed_date: str, frequency_days: int, performed_by: str = "", cost: float = 0.0, notes: str = "") -> str:
    """Registra un mantenimiento realizado y reprograma automáticamente la
    próxima fecha (performed_date + frequency_days)."""
    initialize_database()
    log_id = f"LOG-{uuid4().hex[:8].upper()}"
    next_due = next_due_date_after(date.fromisoformat(performed_date), frequency_days).isoformat()
    with connect() as conn:
        conn.execute(
            "INSERT INTO maintenance_logs(log_id, plan_id, machine_id, performed_date, performed_by, cost, notes, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (log_id, plan_id, machine_id, performed_date, performed_by.strip(), cost, notes.strip(), date.today().isoformat()),
        )
        conn.execute(
            "UPDATE maintenance_plans SET last_done_date = ?, next_due_date = ? WHERE plan_id = ?",
            (performed_date, next_due, plan_id),
        )
    record_audit_event("produccion", "maintenance_plans", plan_id, "maintenance_done", after={"performed_date": performed_date, "cost": cost})
    return log_id


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def render_machine_maintenance() -> None:
    render_page_header("Mantenimiento preventivo", "Calendario de mantenimiento por máquina, con alertas de atraso.")
    st.caption("La frecuencia recomendada debe salir del manual de cada máquina — este módulo solo ayuda a no perderla de vista.")

    machines = list_machines()
    if not machines:
        st.info("Registra máquinas en Costeo por procesos antes de crear planes de mantenimiento.")
        return

    plans = list_plans()
    today = date.today()
    overdue = overdue_plans(plans, today)
    due_soon = due_soon_plans(plans, today)

    cols = st.columns(3)
    cols[0].metric("Planes activos", str(len([plan for plan in plans if plan.get("active")])))
    cols[1].metric("Atrasados", str(len(overdue)))
    cols[2].metric("Próximos 7 días", str(len(due_soon)))

    if overdue:
        st.error(f"{len(overdue)} mantenimiento(s) atrasado(s): " + ", ".join(f"{plan['machine_name']} · {plan['task_name']}" for plan in overdue))
    elif due_soon:
        st.warning(f"{len(due_soon)} mantenimiento(s) próximos a vencer en los siguientes 7 días.")
    else:
        st.success("No hay mantenimientos atrasados ni próximos a vencer.")

    with st.expander("Crear plan de mantenimiento", expanded=not plans):
        machine_options = {machine["name"]: machine for machine in machines}
        with st.form("plan_form", clear_on_submit=True):
            machine_label = st.selectbox("Máquina", tuple(machine_options.keys()))
            task_col, frequency_col = st.columns(2)
            task_name = task_col.selectbox("Tarea", TASK_SUGGESTIONS)
            frequency_days = frequency_col.number_input("Frecuencia (días)", min_value=1, value=30, step=1)
            notes = st.text_area("Notas (opcional)")
            submitted = st.form_submit_button("Crear plan", type="primary", use_container_width=True)
        if submitted:
            create_plan(machine_options[machine_label]["machine_id"], task_name, int(frequency_days), notes)
            st.success("Plan de mantenimiento creado.")
            st.rerun()

    for plan in plans:
        with st.container(border=True):
            remaining = days_until_due(plan, today)
            cols = st.columns([3, 2, 2, 2])
            cols[0].markdown(f"**{plan['machine_name']}** · {plan['task_name']}")
            cols[1].write(f"Cada {plan['frequency_days']} días")
            if remaining < 0:
                cols[2].error(f"Atrasado {-remaining} día(s)")
            elif remaining <= 7:
                cols[2].warning(f"Vence en {remaining} día(s)")
            else:
                cols[2].write(f"Vence en {remaining} día(s)")

            with cols[3].popover("Registrar mantenimiento"):
                with st.form(f"log_form_{plan['plan_id']}", clear_on_submit=True):
                    performed_date = st.date_input("Fecha realizada", value=today, key=f"date_{plan['plan_id']}")
                    performed_by = st.text_input("Realizado por", key=f"by_{plan['plan_id']}")
                    cost = st.number_input("Costo", min_value=0.0, step=1.0, key=f"cost_{plan['plan_id']}")
                    log_notes = st.text_input("Notas", key=f"notes_{plan['plan_id']}")
                    log_submitted = st.form_submit_button("Guardar", type="primary")
                if log_submitted:
                    register_maintenance(plan["plan_id"], plan["machine_id"], performed_date.isoformat(), plan["frequency_days"], performed_by, cost, log_notes)
                    st.success("Mantenimiento registrado. Próxima fecha reprogramada.")
                    st.rerun()

            logs = logs_for_plan(plan["plan_id"])
            if logs:
                total_cost = sum(float(log.get("cost", 0.0)) for log in logs)
                st.caption(f"Último: {logs[0]['performed_date']} · {len(logs)} mantenimiento(s) registrados · {format_money(total_cost)} acumulado")

    render_info_card("Alcance", "Calendario y bitácora de mantenimiento por máquina. No reemplaza el manual del fabricante.", "PRODUCCIÓN")


app_shell.FUNCTIONAL_MODULES["Mantenimiento preventivo"] = render_machine_maintenance
