"""Pruebas de activos productivos (`src/assets.py`)."""

from __future__ import annotations

import pytest

from src.assets import Asset, _asset_from_dict, _update_asset_units, landed_acquisition_cost


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


# ---------------------------------------------------------------------------
# landed_acquisition_cost — costo real del equipo (envío, aranceles, impuestos)
# ---------------------------------------------------------------------------

def test_landed_acquisition_cost_same_currency_no_conversion():
    # equipo 1000, envío 50, aranceles 30, impuestos 20, tasa 1 => 1100
    cost = landed_acquisition_cost(subtotal=1000.0, shipping=50.0, import_duties=30.0, tax=20.0, exchange_rate=1.0)
    assert cost == 1100.0


def test_landed_acquisition_cost_converts_using_exchange_rate():
    # Compra en VES: equipo 40000, envío 2000, aranceles 1000, impuestos 1000
    # (total 44000 VES), tasa 40 VES por USD => 1100 USD.
    cost = landed_acquisition_cost(subtotal=40000.0, shipping=2000.0, import_duties=1000.0, tax=1000.0, exchange_rate=40.0)
    assert cost == 1100.0


def test_landed_acquisition_cost_includes_all_components_not_just_subtotal():
    only_subtotal = landed_acquisition_cost(1000.0, 0.0, 0.0, 0.0, 1.0)
    with_extras = landed_acquisition_cost(1000.0, 50.0, 30.0, 20.0, 1.0)
    assert with_extras > only_subtotal
    assert with_extras - only_subtotal == 100.0


# ---------------------------------------------------------------------------
# _asset_from_dict — normaliza el nuevo detalle de compra con compatibilidad
# ---------------------------------------------------------------------------

def test_asset_from_dict_reads_purchase_detail_fields():
    raw = {
        "asset_id": "AST-1", "name": "Silhouette Cameo 5", "category": "Equipo de corte",
        "acquisition_cost": 1100.0, "lifetime_units": 5000, "current_units": 0,
        "supplier": "Distribuidora ABC", "purchase_currency": "VES", "exchange_rate_used": 40.0,
        "payment_method": "Zelle", "acquisition_subtotal": 40000.0, "shipping_cost": 2000.0,
        "import_duties": 1000.0, "tax_amount": 1000.0, "invoice_reference": "F-00123",
        "purchase_date": "2026-07-01", "warranty_until": "2027-07-01",
    }
    asset = _asset_from_dict(raw)
    assert asset.supplier == "Distribuidora ABC"
    assert asset.purchase_currency == "VES"
    assert asset.exchange_rate_used == 40.0
    assert asset.payment_method == "Zelle"
    assert asset.acquisition_subtotal == 40000.0
    assert asset.shipping_cost == 2000.0
    assert asset.import_duties == 1000.0
    assert asset.tax_amount == 1000.0
    assert asset.invoice_reference == "F-00123"
    assert asset.purchase_date == "2026-07-01"
    assert asset.warranty_until == "2027-07-01"


def test_asset_from_dict_defaults_purchase_detail_when_missing():
    """Compatibilidad con activos registrados antes de este detalle:
    no debe fallar, y debe completar con valores por defecto sensatos."""
    raw = {"asset_id": "AST-OLD", "name": "Impresora vieja", "acquisition_cost": 300.0, "lifetime_units": 1000}
    asset = _asset_from_dict(raw)
    assert asset.supplier == ""
    assert asset.exchange_rate_used == 1.0
    assert asset.acquisition_subtotal == 0.0
    assert asset.purchase_total_in_purchase_currency == 0.0


def test_purchase_total_in_purchase_currency_sums_all_components():
    asset = _make_asset(acquisition_subtotal=1000.0, shipping_cost=50.0, import_duties=30.0, tax_amount=20.0)
    assert asset.purchase_total_in_purchase_currency == 1100.0


# ---------------------------------------------------------------------------
# has_import_duties — marcar cuándo un equipo SÍ pagó aranceles
# ---------------------------------------------------------------------------

def test_asset_from_dict_defaults_has_import_duties_to_false():
    """Compatibilidad con activos ya registrados antes de esta casilla: no
    debe asumir que pagaron aranceles si nunca se especificó."""
    raw = {"asset_id": "AST-OLD", "name": "Impresora vieja", "acquisition_cost": 300.0, "lifetime_units": 1000}
    asset = _asset_from_dict(raw)
    assert asset.has_import_duties is False
    assert asset.import_duties == 0.0


def test_asset_from_dict_reads_has_import_duties_true():
    raw = {
        "asset_id": "AST-1", "name": "Cameo importada", "acquisition_cost": 1000.0, "lifetime_units": 5000,
        "has_import_duties": True, "import_duties": 150.0,
    }
    asset = _asset_from_dict(raw)
    assert asset.has_import_duties is True
    assert asset.import_duties == 150.0


def test_landed_acquisition_cost_unaffected_by_flag_only_by_amount():
    """El flag has_import_duties es solo para la interfaz/registro; el
    cálculo del costo real siempre depende del monto que se le pase (0 si
    no aplica)."""
    with_flag_off = landed_acquisition_cost(1000.0, 0.0, 0.0, 0.0, 1.0)
    with_flag_on_but_zero = landed_acquisition_cost(1000.0, 0.0, 0.0, 0.0, 1.0)
    assert with_flag_off == with_flag_on_but_zero == 1000.0
