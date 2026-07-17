"""Pruebas del análisis de costo total de propiedad (`src/assets_control.py`).

Cubren las funciones puras de la capa superior de activos: la unión de las
dos bitácoras de mantenimiento, el costo total de propiedad (TCO), el costo
real por unidad (depreciación + mantenimiento) y la señal de reponer-vs-reparar.
"""

from __future__ import annotations

from src.assets import Asset
from src.assets_control import (
    REPLACE_SIGNAL_RATIO,
    actual_cost_per_unit,
    build_tco_report,
    combine_maintenance_logs,
    fleet_totals,
    maintenance_cost_for,
    maintenance_events_for,
    maintenance_ratio,
    planned_cost_per_unit,
    remaining_useful_units,
    should_consider_replacement,
    total_cost_of_ownership,
)


def _make_asset(**overrides) -> Asset:
    base = dict(
        asset_id="AST-1",
        name="Impresora HP",
        category="Impresora",
        acquisition_cost=1000.0,
        lifetime_units=1000,
        current_units=0,
    )
    base.update(overrides)
    return Asset(**base)


# ---------------------------------------------------------------------------
# combine_maintenance_logs / maintenance_cost_for — unir las dos bitácoras
# ---------------------------------------------------------------------------

def test_combine_maintenance_logs_merges_both_sources():
    inline = [{"asset_id": "AST-1", "cost": 30.0}]
    governance = [{"asset_id": "AST-1", "cost": 20.0}]
    combined = combine_maintenance_logs(inline, governance)
    assert len(combined) == 2


def test_combine_maintenance_logs_ignores_non_dict_rows():
    combined = combine_maintenance_logs([{"asset_id": "AST-1", "cost": 5.0}, "basura", 42], [])
    assert combined == [{"asset_id": "AST-1", "cost": 5.0}]


def test_maintenance_cost_sums_across_both_logs_for_the_right_asset():
    """El costo de mantenimiento estaba partido en dos bitácoras; aquí debe
    sumarse completo, y solo del activo pedido."""
    combined = combine_maintenance_logs(
        [{"asset_id": "AST-1", "cost": 30.0}, {"asset_id": "AST-2", "cost": 99.0}],
        [{"asset_id": "AST-1", "cost": 20.0}],
    )
    assert maintenance_cost_for("AST-1", combined) == 50.0
    assert maintenance_cost_for("AST-2", combined) == 99.0


def test_maintenance_cost_tolerates_missing_or_bad_cost():
    combined = [{"asset_id": "AST-1"}, {"asset_id": "AST-1", "cost": "no-numero"}, {"asset_id": "AST-1", "cost": 12.0}]
    assert maintenance_cost_for("AST-1", combined) == 12.0


def test_maintenance_events_counts_entries_across_logs():
    combined = combine_maintenance_logs(
        [{"asset_id": "AST-1", "cost": 1.0}, {"asset_id": "AST-1", "cost": 2.0}],
        [{"asset_id": "AST-1", "cost": 3.0}, {"asset_id": "AST-2", "cost": 4.0}],
    )
    assert maintenance_events_for("AST-1", combined) == 3
    assert maintenance_events_for("AST-2", combined) == 1


# ---------------------------------------------------------------------------
# total_cost_of_ownership
# ---------------------------------------------------------------------------

def test_tco_is_acquisition_plus_maintenance():
    asset = _make_asset(acquisition_cost=1000.0)
    assert total_cost_of_ownership(asset, 250.0) == 1250.0


def test_tco_ignores_negative_maintenance():
    asset = _make_asset(acquisition_cost=1000.0)
    assert total_cost_of_ownership(asset, -50.0) == 1000.0


# ---------------------------------------------------------------------------
# planned_cost_per_unit / actual_cost_per_unit
# ---------------------------------------------------------------------------

def test_planned_cost_per_unit_spreads_purchase_over_lifetime():
    asset = _make_asset(acquisition_cost=1000.0, lifetime_units=1000)
    assert planned_cost_per_unit(asset) == 1.0


def test_planned_cost_per_unit_zero_when_no_lifetime():
    asset = _make_asset(acquisition_cost=1000.0, lifetime_units=1)
    # lifetime_units mínimo válido es 1; con 1 el costo por unidad es el total
    assert planned_cost_per_unit(asset) == 1000.0


def test_actual_cost_per_unit_adds_maintenance_to_depreciation():
    # 1000 de costo, vida 1000, 100 unidades => depreciación acumulada 100.
    # + 50 de mantenimiento => 150 / 100 unidades = 1.5 por unidad.
    asset = _make_asset(acquisition_cost=1000.0, lifetime_units=1000, current_units=100)
    assert actual_cost_per_unit(asset, 50.0) == 1.5


def test_actual_cost_per_unit_zero_when_no_units_produced():
    """Sin unidades producidas no hay costo por unidad que calcular (evita
    dividir entre cero y mostrar un número enorme engañoso)."""
    asset = _make_asset(acquisition_cost=1000.0, lifetime_units=1000, current_units=0)
    assert actual_cost_per_unit(asset, 200.0) == 0.0


def test_actual_cost_per_unit_exceeds_planned_when_maintenance_is_high():
    asset = _make_asset(acquisition_cost=1000.0, lifetime_units=1000, current_units=100)
    assert actual_cost_per_unit(asset, 500.0) > planned_cost_per_unit(asset)


# ---------------------------------------------------------------------------
# remaining_useful_units
# ---------------------------------------------------------------------------

def test_remaining_useful_units_subtracts_used_from_lifetime():
    asset = _make_asset(lifetime_units=1000, current_units=300)
    assert remaining_useful_units(asset) == 700


def test_remaining_useful_units_never_negative():
    asset = _make_asset(lifetime_units=100, current_units=500)
    assert remaining_useful_units(asset) == 0


# ---------------------------------------------------------------------------
# maintenance_ratio / should_consider_replacement
# ---------------------------------------------------------------------------

def test_maintenance_ratio_is_fraction_of_purchase_cost():
    asset = _make_asset(acquisition_cost=1000.0)
    assert maintenance_ratio(asset, 250.0) == 0.25


def test_maintenance_ratio_zero_when_no_purchase_cost():
    """Equipo heredado sin costo de compra: sin denominador válido, la razón
    es 0 y no debe disparar la señal de reposición por sí sola."""
    asset = _make_asset(acquisition_cost=0.0, no_purchase_cost=True)
    assert maintenance_ratio(asset, 500.0) == 0.0
    assert should_consider_replacement(asset, 500.0) is False


def test_should_consider_replacement_triggers_at_threshold():
    asset = _make_asset(acquisition_cost=1000.0)
    at_threshold = 1000.0 * REPLACE_SIGNAL_RATIO
    assert should_consider_replacement(asset, at_threshold) is True
    assert should_consider_replacement(asset, at_threshold - 1) is False


# ---------------------------------------------------------------------------
# build_tco_report / fleet_totals
# ---------------------------------------------------------------------------

def test_build_tco_report_sorts_by_tco_descending():
    cheap = _make_asset(asset_id="AST-cheap", name="Barata", acquisition_cost=200.0)
    pricey = _make_asset(asset_id="AST-pricey", name="Cara", acquisition_cost=2000.0)
    combined = [{"asset_id": "AST-cheap", "cost": 10.0}]
    report = build_tco_report([cheap, pricey], combined)
    assert [row["asset_id"] for row in report] == ["AST-pricey", "AST-cheap"]


def test_build_tco_report_includes_maintenance_from_both_logs():
    asset = _make_asset(asset_id="AST-1", acquisition_cost=1000.0)
    combined = combine_maintenance_logs(
        [{"asset_id": "AST-1", "cost": 30.0}],
        [{"asset_id": "AST-1", "cost": 20.0}],
    )
    report = build_tco_report([asset], combined)
    assert report[0]["maintenance_cost"] == 50.0
    assert report[0]["tco"] == 1050.0
    assert report[0]["maintenance_events"] == 2


def test_fleet_totals_aggregates_report():
    a = _make_asset(asset_id="AST-1", acquisition_cost=1000.0, lifetime_units=1000, current_units=1000)
    b = _make_asset(asset_id="AST-2", acquisition_cost=500.0)
    combined = [{"asset_id": "AST-1", "cost": 600.0}]  # 60% de la compra => candidato
    report = build_tco_report([a, b], combined)
    totals = fleet_totals(report)
    assert totals["asset_count"] == 2
    assert totals["total_acquisition"] == 1500.0
    assert totals["total_maintenance"] == 600.0
    assert totals["total_tco"] == 2100.0
    assert totals["replacement_candidates"] == 1
