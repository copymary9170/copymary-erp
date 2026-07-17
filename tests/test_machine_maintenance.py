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
# Presets por tipo de equipo del taller (Cameo, sublimación, prensa, laminadora)
# ---------------------------------------------------------------------------

def test_preset_group_recognizes_cameo_plotter():
    assert mm.preset_group_for_machine("Silhouette Cameo 4", "Corte") == "Plotter de corte (Cameo / Silhouette)"


def test_preset_group_recognizes_sublimation_printer():
    assert mm.preset_group_for_machine("Epson EcoTank L3210", "Sublimación") == "Impresora de sublimación (tanque / EcoTank)"


def test_preset_group_recognizes_heat_press():
    assert mm.preset_group_for_machine("Prensa plana 40x60", "Sublimación por calor") == "Prensa / plancha térmica"


def test_preset_group_unknown_returns_empty():
    assert mm.preset_group_for_machine("Máquina rara XYZ", "Otro") == ""


def test_presets_for_cameo_include_blade_change_by_usage():
    presets = mm.presets_for_machine("Cameo 4", "Corte")
    blade = next(p for p in presets if "cuchilla" in p["task_name"].casefold())
    assert blade["usage_metric"] == "Metros de corte"
    assert blade["usage_frequency"] > 0
    assert blade["frequency_days"] == 0  # la cuchilla se gasta por uso, no por calendario
    assert blade["wear_part"] == "Cuchilla"


def test_presets_for_unknown_machine_offer_full_catalog():
    presets = mm.presets_for_machine("Desconocida", "Otro")
    total = sum(len(group) for group in mm.EQUIPMENT_PRESETS.values())
    assert len(presets) == total


# ---------------------------------------------------------------------------
# Desgaste por USO (además de por tiempo)
# ---------------------------------------------------------------------------

def _usage_plan(**overrides) -> dict:
    base = {
        "plan_id": "MNT-U", "active": 1, "next_due_date": (TODAY + timedelta(days=90)).isoformat(),
        "frequency_days": 0, "usage_metric": "Metros de corte", "usage_frequency": 500.0,
        "current_usage": 0.0, "next_due_usage": 500.0,
    }
    base.update(overrides)
    return base


def test_usage_until_due_returns_remaining_units():
    plan = _usage_plan(current_usage=480.0, next_due_usage=500.0)
    assert mm.usage_until_due(plan) == 20.0


def test_usage_until_due_none_when_no_usage_trigger():
    plan = _usage_plan(usage_frequency=0.0)
    assert mm.usage_until_due(plan) is None


def test_is_overdue_by_usage_true_when_reading_reaches_target():
    plan = _usage_plan(current_usage=520.0, next_due_usage=500.0)
    assert mm.is_overdue_by_usage(plan) is True


def test_is_due_soon_by_usage_within_last_10_percent():
    plan = _usage_plan(current_usage=460.0, next_due_usage=500.0)  # faltan 40 de 500 (8%)
    assert mm.is_due_soon_by_usage(plan) is True


def test_is_due_soon_by_usage_false_when_plenty_left():
    plan = _usage_plan(current_usage=100.0, next_due_usage=500.0)
    assert mm.is_due_soon_by_usage(plan) is False


def test_next_due_usage_after_adds_frequency():
    assert mm.next_due_usage_after(480.0, 500.0) == 980.0


# ---------------------------------------------------------------------------
# Estado combinado: lo que ocurra primero (tiempo o uso)
# ---------------------------------------------------------------------------

def test_is_overdue_combined_triggers_on_usage_even_if_time_is_fine():
    """Un plan con fecha lejana pero contador pasado debe salir atrasado."""
    plan = _usage_plan(next_due_date=(TODAY + timedelta(days=80)).isoformat(), current_usage=600.0, next_due_usage=500.0)
    assert mm.is_overdue(plan, TODAY) is False
    assert mm.is_overdue_combined(plan, TODAY) is True


def test_is_overdue_combined_triggers_on_time_even_if_usage_is_fine():
    plan = _usage_plan(next_due_date=(TODAY - timedelta(days=1)).isoformat(), current_usage=10.0, next_due_usage=500.0)
    assert mm.is_overdue_by_usage(plan) is False
    assert mm.is_overdue_combined(plan, TODAY) is True


def test_plan_alert_reports_usage_reason_when_usage_overdue():
    plan = _usage_plan(next_due_date=(TODAY + timedelta(days=80)).isoformat(), current_usage=600.0, next_due_usage=500.0)
    level, reason = mm.plan_alert(plan, TODAY)
    assert level == "overdue"
    assert "uso" in reason.casefold()


def test_plan_alert_ok_when_nothing_pending():
    plan = _usage_plan(next_due_date=(TODAY + timedelta(days=80)).isoformat(), current_usage=100.0, next_due_usage=500.0)
    level, _reason = mm.plan_alert(plan, TODAY)
    assert level == "ok"


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


def test_create_usage_based_plan_sets_next_due_usage(isolated_database):
    _create_machine("MCH-1", "Cameo 4")
    plan_id = mm.create_plan(
        "MCH-1", "Cambiar cuchilla", frequency_days=0,
        usage_metric="Metros de corte", usage_frequency=500.0, current_usage=120.0,
    )
    plan = next(p for p in mm.list_plans() if p["plan_id"] == plan_id)
    assert plan["usage_metric"] == "Metros de corte"
    assert plan["current_usage"] == 120.0
    assert plan["next_due_usage"] == 620.0  # 120 + 500


def test_update_usage_reading_moves_plan_toward_due(isolated_database):
    _create_machine("MCH-1", "Cameo 4")
    plan_id = mm.create_plan("MCH-1", "Cambiar cuchilla", frequency_days=0, usage_metric="Metros de corte", usage_frequency=500.0)
    mm.update_usage_reading(plan_id, 490.0)
    plan = next(p for p in mm.list_plans() if p["plan_id"] == plan_id)
    assert plan["current_usage"] == 490.0
    assert mm.is_due_soon_by_usage(plan) is True  # faltan 10 de 500


def test_register_maintenance_reschedules_usage_from_service_reading(isolated_database):
    _create_machine("MCH-1", "Cameo 4")
    plan_id = mm.create_plan("MCH-1", "Cambiar cuchilla", frequency_days=0, usage_metric="Metros de corte", usage_frequency=500.0)
    mm.update_usage_reading(plan_id, 510.0)  # ya vencido por uso

    mm.register_maintenance(plan_id, "MCH-1", "2026-07-11", frequency_days=0, cost=8.0, usage_at_service=510.0)

    plan = next(p for p in mm.list_plans() if p["plan_id"] == plan_id)
    assert plan["last_done_usage"] == 510.0
    assert plan["next_due_usage"] == 1010.0  # 510 + 500
    assert mm.is_overdue_by_usage(plan) is False  # ya no está vencido tras el servicio
    logs = mm.logs_for_plan(plan_id)
    assert logs[0]["usage_at_service"] == 510.0


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
