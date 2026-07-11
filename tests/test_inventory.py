"""Pruebas de inventario: valuación de stock y ajustes de existencia."""

from __future__ import annotations

from src import inventory, inventory_movements_enterprise as movements


# ---------------------------------------------------------------------------
# src/inventory.py — InventoryItem y _adjust_stock
# ---------------------------------------------------------------------------

def _make_item(**overrides) -> inventory.InventoryItem:
    base = dict(
        item_id="ITM-1",
        name="Vinil blanco",
        category="Consumible",
        purchase_cost=100.0,
        purchased_quantity=10.0,
        available_quantity=10.0,
        unit_name="metro",
        minimum_stock=2.0,
    )
    base.update(overrides)
    return inventory.InventoryItem(**base)


def test_unit_cost_divides_purchase_cost_by_purchased_quantity():
    item = _make_item(purchase_cost=100.0, purchased_quantity=10.0)
    assert item.unit_cost == 10.0


def test_stock_value_multiplies_available_quantity_by_unit_cost():
    item = _make_item(purchase_cost=100.0, purchased_quantity=10.0, available_quantity=4.0)
    assert item.stock_value == 40.0


def test_is_low_stock_true_when_at_or_below_minimum():
    item = _make_item(available_quantity=2.0, minimum_stock=2.0)
    assert item.is_low_stock is True


def test_is_low_stock_false_when_above_minimum():
    item = _make_item(available_quantity=5.0, minimum_stock=2.0)
    assert item.is_low_stock is False


def test_adjust_stock_entrada_increases_available_quantity():
    items = [_make_item(available_quantity=10.0)]
    updated = inventory._adjust_stock(items, "ITM-1", "Entrada", 5.0)
    assert updated[0].available_quantity == 15.0


def test_adjust_stock_salida_decreases_available_quantity():
    items = [_make_item(available_quantity=10.0)]
    updated = inventory._adjust_stock(items, "ITM-1", "Salida", 3.0)
    assert updated[0].available_quantity == 7.0


def test_adjust_stock_salida_does_not_go_below_zero():
    items = [_make_item(available_quantity=2.0)]
    updated = inventory._adjust_stock(items, "ITM-1", "Salida", 100.0)
    assert updated[0].available_quantity == 0.0


def test_adjust_stock_only_affects_the_targeted_item():
    items = [_make_item(item_id="ITM-1", available_quantity=10.0), _make_item(item_id="ITM-2", available_quantity=10.0)]
    updated = inventory._adjust_stock(items, "ITM-1", "Entrada", 5.0)
    by_id = {item.item_id: item.available_quantity for item in updated}
    assert by_id["ITM-1"] == 15.0
    assert by_id["ITM-2"] == 10.0


# ---------------------------------------------------------------------------
# src/inventory_movements_enterprise.py — valuación de movimientos
# ---------------------------------------------------------------------------

def test_unit_cost_from_item_list():
    items = [{"item_id": "ITM-1", "purchase_cost": 50.0, "purchased_quantity": 5.0}]
    assert movements._unit_cost("ITM-1", items) == 10.0


def test_unit_cost_missing_item_defaults_to_zero():
    assert movements._unit_cost("NO-EXISTE", items=[]) == 0.0


def test_movement_value_multiplies_quantity_by_unit_cost():
    items = [{"item_id": "ITM-1", "purchase_cost": 50.0, "purchased_quantity": 5.0}]
    movement = {"item_id": "ITM-1", "quantity": 3.0}
    assert movements._movement_value(movement, items) == 30.0  # 3 * 10.0


def test_available_reads_available_quantity_field():
    assert movements._available({"available_quantity": 7.0}) == 7.0


def test_available_falls_back_to_quantity_field():
    """Compatibilidad con registros antiguos que usaban `quantity` en vez de `available_quantity`."""
    assert movements._available({"quantity": 3.0}) == 3.0


def test_num_parses_valid_numeric_strings():
    assert movements._num("12.5") == 12.5


def test_num_returns_default_for_invalid_input():
    assert movements._num("no-es-un-numero", default=9.0) == 9.0
    assert movements._num(None, default=0.0) == 0.0
