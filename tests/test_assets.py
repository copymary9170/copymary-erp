"""Pruebas de activos productivos (`src/assets.py`)."""

from __future__ import annotations

import pytest

from src.assets import Asset, _update_asset_units


def _make_asset(**overrides) -> Asset:
    base = dict(
        asset_id="AST-1",
        name="Impresora HP",
        category="Impresión",
        acquisition_cost=1200.0,
        lifetime_units=30000,
        current_units=0,
    )
    base.update(overrides)
    return Asset(**base)


def test_depreciation_per_unit_divides_cost_by_lifetime():
    asset = _make_asset(acquisition_cost=3000.0, lifetime_units=1000)
    assert asset.depreciation_per_unit == 3.0


def test_accumulated_depreciation_multiplies_used_units():
    asset = _make_asset(acquisition_cost=3000.0, lifetime_units=1000, current_units=200)
    assert asset.accumulated_depreciation == 600.0


def test_accumulated_depreciation_caps_at_lifetime_units():
    """No debe depreciar más allá del 100%, aunque current_units exceda lifetime_units."""
    asset = _make_asset(acquisition_cost=1000.0, lifetime_units=100, current_units=500)
    assert asset.accumulated_depreciation == 1000.0


def test_remaining_value_never_goes_negative():
    asset = _make_asset(acquisition_cost=500.0, lifetime_units=100, current_units=500)
    assert asset.remaining_value == 0.0


def test_remaining_value_subtracts_depreciation_from_cost():
    asset = _make_asset(acquisition_cost=1000.0, lifetime_units=100, current_units=40)
    assert asset.remaining_value == 600.0


def test_usage_percent_caps_at_100():
    asset = _make_asset(lifetime_units=100, current_units=250)
    assert asset.usage_percent == 100.0


def test_usage_percent_calculates_proportion():
    asset = _make_asset(lifetime_units=200, current_units=50)
    assert asset.usage_percent == 25.0


def test_depreciation_per_unit_raises_on_zero_lifetime():
    """Comportamiento documentado: la UI exige lifetime_units >= 1 (ver assets.py),
    así que un 0 aquí es un dato inválido que debe fallar de forma ruidosa,
    no devolver un número engañoso."""
    asset = _make_asset(lifetime_units=0)
    with pytest.raises(ZeroDivisionError):
        asset.depreciation_per_unit


def test_update_asset_units_adds_to_the_right_asset():
    assets = [_make_asset(asset_id="AST-1", current_units=10), _make_asset(asset_id="AST-2", current_units=10)]
    updated = _update_asset_units(assets, "AST-1", 5)
    by_id = {asset.asset_id: asset.current_units for asset in updated}
    assert by_id["AST-1"] == 15
    assert by_id["AST-2"] == 10


def test_update_asset_units_with_unknown_id_leaves_list_unchanged():
    assets = [_make_asset(asset_id="AST-1", current_units=10)]
    updated = _update_asset_units(assets, "NO-EXISTE", 5)
    assert updated[0].current_units == 10
