"""Pruebas de mantenimiento preventivo de máquinas (`src/machine_maintenance.py`)."""

from __future__ import annotations

from datetime import date, timedelta

from src import machine_maintenance as mm
from src.erp_database import connect, initialize_database

TODAY = date(2026, 7, 11)


def _plan(**overrides) -> dict:
    base = {"plan_id": "MNT-1", "active": 1, "next_due_date": TODAY.isoformat()}
    base.update(overrides)
    return base


def _create_machine(machine_id: str = "MCH-1", name: str = "Sublimadora") -> None:
    initialize_database()
    with connect() as conn:
        conn.execute(
            "INSERT INTO production_machines(machine_id, name, category, acquisition_cost, useful_life_hours, power_kw, maintenance_cost_per_hour, active, created_at_utc) VALUES (?, ?, 'Sublimación', 500.0, 5000.0, 0.5, 0.1, 1, '2026-01-01')",
            (machine_id, name),
        )


# ---------------------------------------------------------------------------
# Cálculo puro
# ---------------------------------------------------------------------------

def test_days_until_due_positive_for_future_date():
    plan = _plan(next_due_date=(TODAY + timedelta(days=10)).isoformat())
    assert mm.days_until_due(plan, TODAY) == 10


def test_days_until_due_negative_for_past_date():
    plan = _plan(next_due_date=(TODAY - timedelta(days=3)).isoformat())
    assert mm.days_until_due(plan, TODAY) == -3


def test_is_overdue_true_for_past_due_date():
    plan = _plan(next_due_date=(TODAY - timedelta(days=1)).isoformat())
    assert mm.is_overdue(plan, TODAY) is True


def test_is_overdue_false_for_today_or_future():
    assert mm.is_overdue(_plan(next_due_date=TODAY.isoformat()), TODAY) is False
    assert mm.is_overdue(_plan(next_due_date=(TODAY + timedelta(days=1)).isoformat()), TODAY) is False


def test_is_due_soon_true_within_default_window():
    plan = _plan(next_due_date=(TODAY + timedelta(days=5)).isoformat())
    assert mm.is_due_soon(plan, TODAY) is True


def test_is_due_soon_false_beyond_window():
    plan = _plan(next_due_date=(TODAY + timedelta(days=20)).isoformat())
    assert mm.is_due_soon(plan, TODAY) is False


def test_is_due_soon_false_when_already_overdue():
    """Atrasado es una categoría distinta de 'próximo a vencer'."""
    plan = _plan(next_due_date=(TODAY - timedelta(days=1)).isoformat())
    assert mm.is_due_soon(plan, TODAY) is False


def test_overdue_plans_filters_inactive():
    plans = [
        _plan(plan_id="P1", active=1, next_due_date=(TODAY - timedelta(days=1)).isoformat()),
        _plan(plan_id="P2", active=0, next_due_date=(TODAY - timedelta(days=1)).isoformat()),
    ]
    overdue = mm.overdue_plans(plans, TODAY)
    assert len(overdue) == 1
    assert overdue[0]["plan_id"] == "P1"


def test_next_due_date_after_adds_frequency_days():
    result = mm.next_due_date_after(TODAY, frequency_days=15)
    assert result == TODAY + timedelta(days=15)


# ---------------------------------------------------------------------------
# Flujo completo con base de datos
# ---------------------------------------------------------------------------

def test_create_plan_sets_initial_due_date(isolated_database):
    _create_machine()
    plan_id = mm.create_plan("MCH-1", "Limpieza de cabezales", frequency_days=15)

    plans = mm.list_plans()
    assert len(plans) == 1
    assert plans[0]["plan_id"] == plan_id
    assert plans[0]["machine_name"] == "Sublimadora"
    assert plans[0]["last_done_date"] is None


def test_register_maintenance_reschedules_next_due_date(isolated_database):
    _create_machine()
    plan_id = mm.create_plan("MCH-1", "Limpieza de cabezales", frequency_days=15)

    performed = "2026-07-11"
    mm.register_maintenance(plan_id, "MCH-1", performed, frequency_days=15, performed_by="Ana", cost=10.0)

    plans = mm.list_plans()
    assert plans[0]["last_done_date"] == performed
    assert plans[0]["next_due_date"] == "2026-07-26"


def test_register_maintenance_creates_log_entry(isolated_database):
    _create_machine()
    plan_id = mm.create_plan("MCH-1", "Cambio de cuchilla", frequency_days=30)

    mm.register_maintenance(plan_id, "MCH-1", "2026-07-11", frequency_days=30, performed_by="Ana", cost=25.0, notes="Cuchilla 45°")

    logs = mm.logs_for_plan(plan_id)
    assert len(logs) == 1
    assert logs[0]["performed_by"] == "Ana"
    assert logs[0]["cost"] == 25.0
    assert logs[0]["notes"] == "Cuchilla 45°"


def test_overdue_plan_becomes_current_after_maintenance_registered(isolated_database):
    """Integración: un plan atrasado debe dejar de estarlo tras registrar el mantenimiento."""
    _create_machine()
    plan_id = mm.create_plan("MCH-1", "Limpieza de cabezales", frequency_days=15)
    past_due = (date.today() - timedelta(days=3)).isoformat()
    with connect() as conn:
        conn.execute("UPDATE maintenance_plans SET next_due_date = ? WHERE plan_id = ?", (past_due, plan_id))

    plans = mm.list_plans()
    assert mm.is_overdue(plans[0], date.today()) is True

    mm.register_maintenance(plan_id, "MCH-1", date.today().isoformat(), frequency_days=15)

    plans = mm.list_plans()
    assert mm.is_overdue(plans[0], date.today()) is False


def test_all_maintenance_logs_returns_every_registered_maintenance(isolated_database):
    """all_maintenance_logs() agrega los mantenimientos de todas las máquinas y
    planes, para poder sumarlos en reportes como el Estado de Resultados."""
    _create_machine("MCH-1", "Sublimadora")
    plan_a = mm.create_plan("MCH-1", "Limpieza de cabezales", frequency_days=15)
    plan_b = mm.create_plan("MCH-1", "Calibración", frequency_days=30)
    mm.register_maintenance(plan_a, "MCH-1", "2026-07-05", frequency_days=15, cost=10.0)
    mm.register_maintenance(plan_b, "MCH-1", "2026-07-08", frequency_days=30, cost=25.0)

    logs = mm.all_maintenance_logs()
    assert len(logs) == 2
    assert sum(float(log["cost"]) for log in logs) == 35.0
    assert {log["performed_date"] for log in logs} == {"2026-07-05", "2026-07-08"}


def test_all_maintenance_logs_empty_when_none_registered(isolated_database):
    assert mm.all_maintenance_logs() == []


def test_list_machines_excludes_inactive(isolated_database):
    _create_machine("MCH-1", "Activa")
    with connect() as conn:
        conn.execute(
            "INSERT INTO production_machines(machine_id, name, category, acquisition_cost, useful_life_hours, power_kw, maintenance_cost_per_hour, active, created_at_utc) VALUES ('MCH-2', 'Inactiva', 'Corte', 100.0, 1000.0, 0.1, 0.05, 0, '2026-01-01')"
        )

    machines = mm.list_machines()
    assert len(machines) == 1
    assert machines[0]["name"] == "Activa"
