"""Pruebas de mantenimiento preventivo de máquinas (`src/machine_maintenance.py`)."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

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


# --- Catálogo ampliado del taller: 3D, láser, PVC, térmica, tatuajes, etc. ---

def test_preset_group_recognizes_3d_printer():
    assert mm.preset_group_for_machine("Creality Ender 3 V2", "Impresión 3D") == "Impresora 3D (filamento / resina)"


def test_preset_group_recognizes_laser_engraver():
    assert mm.preset_group_for_machine("Láser CO2 60W", "Grabado") == "Láser de grabado / corte (CO2 / diodo)"


def test_preset_group_laser_engraver_wins_over_laser_printer():
    """'Láser de grabado' contiene 'láser' (palabra de impresora láser); el
    grabador debe ganar por orden de prioridad."""
    assert mm.preset_group_for_machine("Impresora láser de grabado", "Otro") == "Láser de grabado / corte (CO2 / diodo)"


def test_preset_group_recognizes_laser_printer():
    assert mm.preset_group_for_machine("HP LaserJet M111w", "Impresora láser") == "Impresora láser (tóner)"


def test_preset_group_recognizes_cartridge_printer():
    assert mm.preset_group_for_machine("HP DeskJet de cartuchos", "Impresora") == "Impresora de cartuchos (inyección)"


def test_preset_group_recognizes_pvc_card_printer():
    assert mm.preset_group_for_machine("Zebra ZC100", "Impresora de carnets PVC") == "Impresora de carnets / tarjetas PVC"


def test_preset_group_thermal_printer_wins_over_heat_press():
    """'Impresora térmica' contiene 'térmic' (palabra de la prensa); la
    impresora térmica debe ganar por orden de prioridad."""
    assert mm.preset_group_for_machine("Impresora térmica de tickets", "Otro") == "Impresora térmica (tickets / etiquetas)"


def test_preset_group_recognizes_tattoo_stencil_printer():
    assert mm.preset_group_for_machine("Impresora de esténciles para tatuajes", "Otro") == "Impresora de esténciles de tatuaje"


def test_preset_group_guillotine_wins_over_cutting_plotter():
    """'Guillotina de corte' contiene 'corte' (palabra del plotter); la
    guillotina debe ganar por orden de prioridad."""
    assert mm.preset_group_for_machine("Guillotina de corte A4", "Otro") == "Guillotina / cizalla"


def test_preset_group_recognizes_binding_machine():
    assert mm.preset_group_for_machine("Anilladora doble anillo", "Encuadernación") == "Anilladora / encuadernadora"


def test_presets_for_3d_printer_include_nozzle_change_by_hours():
    presets = mm.presets_for_machine("Ender 3", "Impresión 3D")
    nozzle = next(p for p in presets if "boquilla" in p["task_name"].casefold())
    assert nozzle["usage_metric"] == "Horas de uso"
    assert nozzle["wear_part"] == "Boquilla (nozzle)"


def test_presets_for_laser_engraver_include_co2_tube_by_hours():
    presets = mm.presets_for_machine("Láser CO2", "Grabado")
    tube = next(p for p in presets if "tubo" in p["task_name"].casefold())
    assert tube["usage_metric"] == "Horas de uso"
    assert tube["usage_frequency"] > 0
    assert tube["wear_part"] == "Tubo CO2"


def test_presets_for_pvc_printer_include_ribbon_by_cards():
    presets = mm.presets_for_machine("Zebra ZC100", "Impresora de carnets PVC")
    ribbon = next(p for p in presets if "ribbon" in p["task_name"].casefold())
    assert ribbon["usage_metric"] == "Tarjetas impresas"
    assert ribbon["wear_part"] == "Ribbon YMCKO"


def test_all_preset_usage_metrics_exist_in_usage_metrics_catalog():
    """Cada métrica usada por un preset debe existir en USAGE_METRICS, o el
    selector de la interfaz no podría preseleccionarla."""
    for group, presets in mm.EQUIPMENT_PRESETS.items():
        for preset in presets:
            assert preset["usage_metric"] in mm.USAGE_METRICS, f"{group}: {preset['task_name']} usa métrica desconocida {preset['usage_metric']!r}"


def test_every_preset_group_is_reachable_by_keywords():
    """Cada grupo del catálogo debe tener al menos una palabra clave que lo
    active — un grupo inalcanzable jamás se sugeriría a nadie."""
    reachable = {group for group, _keywords in mm._PRESET_KEYWORDS}
    assert reachable == set(mm.EQUIPMENT_PRESETS)


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
# Repuesto planeado: avisar ANTES de quedarse sin él
# ---------------------------------------------------------------------------

def _plan_with_spare_part(**overrides) -> dict:
    base = {
        "plan_id": "MNT-S", "active": 1, "frequency_days": 0,
        "next_due_date": (TODAY + timedelta(days=90)).isoformat(),
        "usage_metric": "", "usage_frequency": 0.0, "current_usage": 0.0, "next_due_usage": 0.0,
        "default_inventory_item_id": "ITM-1",
    }
    base.update(overrides)
    return base


def test_spare_part_stock_for_returns_available_quantity():
    plan = _plan_with_spare_part()
    items = [{"item_id": "ITM-1", "available_quantity": 3.0}]
    assert mm.spare_part_stock_for(plan, items) == 3.0


def test_spare_part_stock_for_none_when_plan_has_no_spare_part():
    plan = _plan_with_spare_part(default_inventory_item_id="")
    assert mm.spare_part_stock_for(plan, [{"item_id": "ITM-1", "available_quantity": 3.0}]) is None


def test_spare_part_stock_for_none_when_item_not_found_in_inventory():
    plan = _plan_with_spare_part()
    assert mm.spare_part_stock_for(plan, []) is None


def test_spare_part_shortage_false_when_maintenance_not_due_soon():
    """Aunque no haya stock, si el mantenimiento está lejos no urge avisar."""
    plan = _plan_with_spare_part(next_due_date=(TODAY + timedelta(days=90)).isoformat())
    items = [{"item_id": "ITM-1", "available_quantity": 0.0}]
    assert mm.spare_part_shortage(plan, items, TODAY) is False


def test_spare_part_shortage_true_when_due_soon_and_no_stock():
    plan = _plan_with_spare_part(next_due_date=(TODAY + timedelta(days=3)).isoformat())
    items = [{"item_id": "ITM-1", "available_quantity": 0.0}]
    assert mm.spare_part_shortage(plan, items, TODAY) is True


def test_spare_part_shortage_true_when_overdue_and_no_stock():
    plan = _plan_with_spare_part(next_due_date=(TODAY - timedelta(days=1)).isoformat())
    items = [{"item_id": "ITM-1", "available_quantity": 0.0}]
    assert mm.spare_part_shortage(plan, items, TODAY) is True


def test_spare_part_shortage_false_when_due_soon_but_stock_available():
    plan = _plan_with_spare_part(next_due_date=(TODAY + timedelta(days=3)).isoformat())
    items = [{"item_id": "ITM-1", "available_quantity": 5.0}]
    assert mm.spare_part_shortage(plan, items, TODAY) is False


def test_spare_part_shortage_false_when_no_spare_part_assigned():
    plan = _plan_with_spare_part(default_inventory_item_id="", next_due_date=(TODAY - timedelta(days=1)).isoformat())
    assert mm.spare_part_shortage(plan, [], TODAY) is False


def test_plans_with_spare_part_shortage_filters_inactive():
    plans = [
        _plan_with_spare_part(plan_id="MNT-A", active=1, next_due_date=(TODAY - timedelta(days=1)).isoformat()),
        _plan_with_spare_part(plan_id="MNT-B", active=0, next_due_date=(TODAY - timedelta(days=1)).isoformat()),
    ]
    items = [{"item_id": "ITM-1", "available_quantity": 0.0}]
    shortages = mm.plans_with_spare_part_shortage(plans, items, TODAY)
    assert len(shortages) == 1
    assert shortages[0]["plan_id"] == "MNT-A"


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


def test_register_maintenance_returns_log_dict_with_defaults(isolated_database):
    """register_maintenance() devuelve el registro creado (no solo el id),
    igual que _log_maintenance de assets.py, para que el llamador pueda
    revisar si el descuento de Inventario funcionó."""
    _create_machine()
    plan_id = mm.create_plan("MCH-1", "Limpieza de cabezales", frequency_days=15)

    entry = mm.register_maintenance(plan_id, "MCH-1", "2026-07-11", frequency_days=15, cost=10.0)

    assert entry["plan_id"] == plan_id
    assert entry["cost"] == 10.0
    assert entry["inventory_item_id"] == ""
    assert entry["inventory_deducted"] is False


def test_register_maintenance_without_inventory_link_does_not_touch_inventory(isolated_database):
    _create_machine()
    plan_id = mm.create_plan("MCH-1", "Limpieza de cabezales", frequency_days=15)
    st.session_state["inventory_registry"] = [{"item_id": "ITM-1", "name": "Cuchilla", "available_quantity": 5.0, "unit_cost": 10.0}]

    entry = mm.register_maintenance(plan_id, "MCH-1", "2026-07-11", frequency_days=15, cost=8.0)

    assert entry["inventory_deducted"] is False
    assert st.session_state["inventory_registry"][0]["available_quantity"] == 5.0


def test_register_maintenance_with_inventory_link_deducts_real_stock(isolated_database):
    """El repuesto real (p. ej. la cuchilla de la Cameo) debe descontarse de
    Inventario al registrar el mantenimiento — antes esta conexión no
    existía en Mantenimiento preventivo (solo en la bitácora de Activos)."""
    _create_machine("MCH-1", "Cameo 4")
    plan_id = mm.create_plan("MCH-1", "Cambiar cuchilla", frequency_days=0, usage_metric="Metros de corte", usage_frequency=500.0)
    st.session_state["inventory_registry"] = [{"item_id": "ITM-1", "name": "Cuchilla Cameo", "available_quantity": 5.0, "unit_cost": 10.0}]

    entry = mm.register_maintenance(
        plan_id, "MCH-1", "2026-07-11", frequency_days=0, cost=0.0,
        inventory_item_id="ITM-1", inventory_quantity=1.0,
    )

    assert entry["inventory_deducted"] is True
    assert st.session_state["inventory_registry"][0]["available_quantity"] == 4.0
    log = mm.logs_for_plan(plan_id)[0]
    assert log["inventory_item_id"] == "ITM-1"
    assert log["inventory_quantity"] == 1.0
    assert log["inventory_deducted"] == 1


def test_register_maintenance_inventory_link_but_item_missing_reports_not_deducted(isolated_database):
    """Si el ítem indicado no existe en ninguna lista de Inventario conocida,
    debe quedar claro que NO se descontó (para poder avisar al usuario),
    sin romper el registro del mantenimiento."""
    _create_machine()
    plan_id = mm.create_plan("MCH-1", "Limpieza de cabezales", frequency_days=15)
    st.session_state.pop("inventory_registry", None)

    entry = mm.register_maintenance(
        plan_id, "MCH-1", "2026-07-11", frequency_days=15, cost=0.0,
        inventory_item_id="NO-EXISTE", inventory_quantity=1.0,
    )

    assert entry["inventory_deducted"] is False


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


def test_create_plan_stores_default_inventory_item_id(isolated_database):
    _create_machine("MCH-1", "Cameo 4")
    plan_id = mm.create_plan(
        "MCH-1", "Cambiar cuchilla", frequency_days=0,
        usage_metric="Metros de corte", usage_frequency=500.0,
        default_inventory_item_id="ITM-1",
    )
    plan = next(p for p in mm.list_plans() if p["plan_id"] == plan_id)
    assert plan["default_inventory_item_id"] == "ITM-1"


def test_create_plan_default_inventory_item_id_defaults_to_empty(isolated_database):
    _create_machine("MCH-1", "Cameo 4")
    plan_id = mm.create_plan("MCH-1", "Limpieza de cabezales", frequency_days=15)
    plan = next(p for p in mm.list_plans() if p["plan_id"] == plan_id)
    assert plan["default_inventory_item_id"] == ""


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


def test_accumulate_usage_for_machine_adds_to_matching_active_plan(isolated_database):
    """El contador de uso puede alimentarse automáticamente (p. ej. desde un
    trabajo costeado confirmado en Costeo por procesos), no solo a mano."""
    _create_machine("MCH-1", "Prensa térmica")
    plan_id = mm.create_plan("MCH-1", "Revisar presión", frequency_days=0, usage_metric="Horas de uso", usage_frequency=100.0, current_usage=10.0)

    updated = mm.accumulate_usage_for_machine("MCH-1", "Horas de uso", 2.5)

    assert updated == 1
    plan = next(p for p in mm.list_plans() if p["plan_id"] == plan_id)
    assert plan["current_usage"] == 12.5


def test_accumulate_usage_for_machine_ignores_plans_with_different_metric(isolated_database):
    _create_machine("MCH-1", "Cameo")
    mm.create_plan("MCH-1", "Cambiar cuchilla", frequency_days=0, usage_metric="Metros de corte", usage_frequency=500.0)

    updated = mm.accumulate_usage_for_machine("MCH-1", "Horas de uso", 5.0)

    assert updated == 0


def test_accumulate_usage_for_machine_ignores_inactive_plans(isolated_database):
    _create_machine("MCH-1", "Prensa térmica")
    plan_id = mm.create_plan("MCH-1", "Revisar presión", frequency_days=0, usage_metric="Horas de uso", usage_frequency=100.0)
    with connect() as conn:
        conn.execute("UPDATE maintenance_plans SET active = 0 WHERE plan_id = ?", (plan_id,))

    updated = mm.accumulate_usage_for_machine("MCH-1", "Horas de uso", 5.0)
    assert updated == 0


def test_accumulate_usage_for_machine_zero_amount_is_noop(isolated_database):
    _create_machine("MCH-1", "Prensa térmica")
    mm.create_plan("MCH-1", "Revisar presión", frequency_days=0, usage_metric="Horas de uso", usage_frequency=100.0)
    assert mm.accumulate_usage_for_machine("MCH-1", "Horas de uso", 0.0) == 0


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
