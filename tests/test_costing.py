"""Pruebas del motor de costeo simple (`src/costing.py`)."""

from __future__ import annotations

from src import costing


def test_asset_depreciation_divides_cost_by_lifetime_units():
    asset = {"acquisition_cost": 1200.0, "lifetime_units": 400}
    assert costing._asset_depreciation(asset) == 3.0


def test_asset_depreciation_avoids_division_by_zero():
    """lifetime_units en 0 no debe romper el cálculo (se fuerza mínimo 1)."""
    asset = {"acquisition_cost": 500.0, "lifetime_units": 0}
    assert costing._asset_depreciation(asset) == 500.0


def test_inventory_unit_cost_divides_purchase_cost_by_quantity():
    item = {"purchase_cost": 50.0, "purchased_quantity": 10.0}
    assert costing._inventory_unit_cost(item) == 5.0


def test_inventory_unit_cost_has_floor_to_avoid_division_by_zero():
    item = {"purchase_cost": 50.0, "purchased_quantity": 0}
    # purchased_quantity se limita a un mínimo de 0.01, no debe lanzar excepción.
    assert costing._inventory_unit_cost(item) == 5000.0


def test_calculate_result_sums_all_cost_components():
    result = costing._calculate_result(
        material_cost=2.0,
        ink_cost=0.5,
        labor_cost=1.0,
        indirect_cost=0.3,
        asset_cost=0.2,
        other_cost=0.0,
        quantity=100,
        profit_margin=40.0,
    )
    assert result.unit_cost == 4.0
    assert result.total_cost == 400.0


def test_calculate_result_applies_profit_margin_to_unit_price():
    result = costing._calculate_result(
        material_cost=4.0,
        ink_cost=0.0,
        labor_cost=0.0,
        indirect_cost=0.0,
        asset_cost=0.0,
        other_cost=0.0,
        quantity=1,
        profit_margin=25.0,
    )
    assert result.unit_price == 5.0  # 4.0 * 1.25


def test_calculate_result_estimated_profit_matches_price_minus_cost():
    result = costing._calculate_result(
        material_cost=10.0,
        ink_cost=0.0,
        labor_cost=0.0,
        indirect_cost=0.0,
        asset_cost=0.0,
        other_cost=0.0,
        quantity=5,
        profit_margin=50.0,
    )
    assert result.estimated_profit == result.total_price - result.total_cost
    assert result.estimated_profit == 25.0  # (10*1.5*5) - (10*5)


def test_calculate_result_with_zero_profit_margin_price_equals_cost():
    result = costing._calculate_result(
        material_cost=3.0,
        ink_cost=0.0,
        labor_cost=0.0,
        indirect_cost=0.0,
        asset_cost=0.0,
        other_cost=0.0,
        quantity=10,
        profit_margin=0.0,
    )
    assert result.unit_price == result.unit_cost
    assert result.estimated_profit == 0.0
