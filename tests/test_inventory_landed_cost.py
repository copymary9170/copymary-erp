"""Pruebas del costo de compra detallado en `src/inventory_enterprise.py`:
envío, impuestos, tasa de cambio, método de pago y contenido físico."""

from __future__ import annotations

import streamlit as st

from src import inventory_enterprise as ie
from src.session_utils import read_list


# ---------------------------------------------------------------------------
# _landed_unit_cost
# ---------------------------------------------------------------------------

def test_landed_unit_cost_same_currency_no_conversion():
    # 100 unidades, material 50, envío 5, impuestos 3, tasa 1 (misma moneda) => 58/100
    unit_cost, total = ie._landed_unit_cost(subtotal=50.0, shipping=5.0, tax=3.0, exchange_rate=1.0, quantity=100.0)
    assert round(unit_cost, 4) == 0.58
    assert total == 58.0


def test_landed_unit_cost_converts_using_exchange_rate():
    # Compra en VES: material 3600, envío 200, impuestos 200 (total 4000 VES),
    # tasa 40 VES por 1 USD => 100 USD landed, entre 50 unidades = 2.0 USD/u.
    unit_cost, total = ie._landed_unit_cost(subtotal=3600.0, shipping=200.0, tax=200.0, exchange_rate=40.0, quantity=50.0)
    assert total == 100.0
    assert unit_cost == 2.0


def test_landed_unit_cost_includes_shipping_and_tax_not_just_material():
    only_material, _ = ie._landed_unit_cost(subtotal=100.0, shipping=0.0, tax=0.0, exchange_rate=1.0, quantity=10.0)
    with_extras, _ = ie._landed_unit_cost(subtotal=100.0, shipping=20.0, tax=10.0, exchange_rate=1.0, quantity=10.0)
    assert with_extras > only_material
    assert round(with_extras - only_material, 4) == 3.0  # (20+10)/10


def test_landed_unit_cost_quantity_clamped_to_at_least_one():
    unit_cost, total = ie._landed_unit_cost(subtotal=50.0, shipping=0.0, tax=0.0, exchange_rate=1.0, quantity=0.0)
    assert unit_cost == 50.0  # se divide entre 1, no entre 0


# ---------------------------------------------------------------------------
# _default_exchange_rate
# ---------------------------------------------------------------------------

def test_default_exchange_rate_is_one_for_same_currency():
    assert ie._default_exchange_rate("USD", "USD") == 1.0


def test_default_exchange_rate_falls_back_to_one_without_data():
    # Sin tasas registradas en la base de datos de la sesión de prueba.
    assert ie._default_exchange_rate("VES", "USD") == 1.0


# ---------------------------------------------------------------------------
# _movement con detalle de compra
# ---------------------------------------------------------------------------

def _purchase_detail(**overrides):
    base = {
        "currency": "USD", "same_currency": True, "exchange_rate": 1.0,
        "payment_method": "Transferencia", "material_subtotal": 45.0,
        "shipping_cost": 5.0, "tax_amount": 0.0, "supplier": "Distribuidora ABC",
    }
    base.update(overrides)
    return base


def test_movement_with_purchase_detail_updates_item_supplier_and_payment_method():
    item = {"item_id": "ITM-1", "name": "Vinil", "available_quantity": 0.0, "unit_cost": 0.0, "purchased_quantity": 1.0}
    ie._movement(item, "Entrada", 10.0, "Compra", 5.0, purchase_detail=_purchase_detail())
    assert item["supplier"] == "Distribuidora ABC"
    assert item["payment_method"] == "Transferencia"
    assert item["purchase_currency"] == "USD"


def test_movement_with_purchase_detail_records_shipping_and_tax_in_history():
    item = {"item_id": "ITM-1", "name": "Vinil", "available_quantity": 0.0, "unit_cost": 0.0, "purchased_quantity": 1.0}
    ie._movement(item, "Entrada", 10.0, "Compra", 5.0, purchase_detail=_purchase_detail(shipping_cost=8.0, tax_amount=2.0))
    movements = read_list("inventory_movements")
    assert movements[0]["shipping_cost"] == 8.0
    assert movements[0]["tax_amount"] == 2.0
    assert movements[0]["supplier"] == "Distribuidora ABC"
    assert movements[0]["payment_method"] == "Transferencia"


def test_movement_without_purchase_detail_does_not_touch_supplier():
    item = {"item_id": "ITM-1", "name": "Vinil", "available_quantity": 10.0, "unit_cost": 1.0, "purchased_quantity": 10.0, "supplier": "Original SA"}
    ie._movement(item, "Salida", 3.0, "Uso interno")
    assert item["supplier"] == "Original SA"


# ---------------------------------------------------------------------------
# _items() — normaliza los nuevos campos con valores por defecto sensatos
# ---------------------------------------------------------------------------

def test_items_normalizes_new_purchase_and_content_fields():
    st.session_state["inventory_registry"] = [{
        "item_id": "ITM-1", "name": "Vinil textil", "available_quantity": 20.0, "unit_cost": 2.0,
        "purchase_currency": "VES", "exchange_rate_used": 40.0, "payment_method": "Zelle",
        "content_type": "area", "content_value": 900.0, "content_unit": "cm²",
    }]
    item = ie._items()[0]
    assert item["purchase_currency"] == "VES"
    assert item["exchange_rate_used"] == 40.0
    assert item["payment_method"] == "Zelle"
    assert item["content_type"] == "area"
    assert item["content_value"] == 900.0
    assert item["content_unit"] == "cm²"


def test_items_defaults_content_type_to_piece_when_missing():
    st.session_state["inventory_registry"] = [{"item_id": "ITM-1", "name": "Tornillos", "available_quantity": 5.0}]
    item = ie._items()[0]
    assert item["content_type"] == "piece"
    assert item["content_value"] == 0.0
    assert item["content_unit"] == ""
