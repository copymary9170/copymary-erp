"""Pruebas del catálogo de producción con receta simple (`src/catalog.py`)."""

from __future__ import annotations

from src import catalog


def _material(item_id, purchase_cost, purchased_quantity, available_quantity, name="Material"):
    return {
        "item_id": item_id,
        "name": name,
        "purchase_cost": purchase_cost,
        "purchased_quantity": purchased_quantity,
        "available_quantity": available_quantity,
        "unit_name": "unidad",
    }


# ---------------------------------------------------------------------------
# _recipe_cost
# ---------------------------------------------------------------------------

def test_recipe_cost_sums_unit_cost_times_quantity():
    inventory = [_material("MAT-1", purchase_cost=100.0, purchased_quantity=10.0, available_quantity=50.0)]
    recipe = [{"item_id": "MAT-1", "quantity": 3.0}]
    # costo unitario = 100/10 = 10.0; 3 unidades = 30.0
    assert catalog._recipe_cost(recipe, inventory) == 30.0


def test_recipe_cost_ignores_components_with_missing_material():
    inventory = [_material("MAT-1", 100.0, 10.0, 50.0)]
    recipe = [{"item_id": "NO-EXISTE", "quantity": 5.0}]
    assert catalog._recipe_cost(recipe, inventory) == 0.0


def test_recipe_cost_sums_multiple_components():
    inventory = [
        _material("MAT-1", 100.0, 10.0, 50.0),  # costo unitario 10
        _material("MAT-2", 20.0, 2.0, 50.0),    # costo unitario 10
    ]
    recipe = [{"item_id": "MAT-1", "quantity": 1.0}, {"item_id": "MAT-2", "quantity": 1.0}]
    assert catalog._recipe_cost(recipe, inventory) == 20.0


# ---------------------------------------------------------------------------
# _max_producible
# ---------------------------------------------------------------------------

def test_max_producible_limited_by_scarcest_material():
    inventory = [
        _material("MAT-1", 1.0, 1.0, available_quantity=10.0),
        _material("MAT-2", 1.0, 1.0, available_quantity=3.0),
    ]
    recipe = [{"item_id": "MAT-1", "quantity": 1.0}, {"item_id": "MAT-2", "quantity": 1.0}]
    assert catalog._max_producible(recipe, inventory) == 3.0


def test_max_producible_with_empty_recipe_is_zero():
    assert catalog._max_producible([], inventory=[]) == 0.0


def test_max_producible_zero_when_material_missing():
    recipe = [{"item_id": "NO-EXISTE", "quantity": 1.0}]
    assert catalog._max_producible(recipe, inventory=[]) == 0.0


def test_max_producible_uses_floor_division():
    """7 disponibles / 2 requeridos por unidad = 3 producibles, no 3.5."""
    inventory = [_material("MAT-1", 1.0, 1.0, available_quantity=7.0)]
    recipe = [{"item_id": "MAT-1", "quantity": 2.0}]
    assert catalog._max_producible(recipe, inventory) == 3.0


# ---------------------------------------------------------------------------
# _can_produce
# ---------------------------------------------------------------------------

def test_can_produce_true_when_enough_stock():
    inventory = [_material("MAT-1", 1.0, 1.0, available_quantity=10.0)]
    recipe = [{"item_id": "MAT-1", "quantity": 2.0}]
    ok, message = catalog._can_produce(recipe, inventory, quantity=3.0)
    assert ok is True
    assert message == ""


def test_can_produce_false_when_not_enough_stock():
    inventory = [_material("MAT-1", 1.0, 1.0, available_quantity=5.0, name="Vinil")]
    recipe = [{"item_id": "MAT-1", "quantity": 2.0}]
    ok, message = catalog._can_produce(recipe, inventory, quantity=3.0)  # necesita 6, hay 5
    assert ok is False
    assert "Vinil" in message


def test_can_produce_false_when_material_missing():
    recipe = [{"item_id": "NO-EXISTE", "quantity": 1.0}]
    ok, message = catalog._can_produce(recipe, inventory=[], quantity=1.0)
    assert ok is False
    assert message != ""


# ---------------------------------------------------------------------------
# _apply_production
# ---------------------------------------------------------------------------

def test_apply_production_consumes_inventory_and_logs_movement():
    inventory = [_material("MAT-1", 1.0, 1.0, available_quantity=10.0)]
    product = {"name": "Taza sublimada", "recipe": [{"item_id": "MAT-1", "quantity": 2.0}]}

    updated_inventory, movements = catalog._apply_production(product, quantity=3.0, inventory=inventory, movements=[])

    assert updated_inventory[0]["available_quantity"] == 4.0  # 10 - (2*3)
    assert len(movements) == 1
    assert movements[0]["movement_type"] == "Salida"
    assert movements[0]["quantity"] == 6.0
    assert movements[0]["previous_quantity"] == 10.0
    assert movements[0]["resulting_quantity"] == 4.0


def test_apply_production_leaves_unrelated_materials_untouched():
    inventory = [
        _material("MAT-1", 1.0, 1.0, available_quantity=10.0),
        _material("MAT-2", 1.0, 1.0, available_quantity=20.0),
    ]
    product = {"name": "Producto", "recipe": [{"item_id": "MAT-1", "quantity": 1.0}]}

    updated_inventory, _ = catalog._apply_production(product, quantity=1.0, inventory=inventory, movements=[])

    by_id = {item["item_id"]: item["available_quantity"] for item in updated_inventory}
    assert by_id["MAT-1"] == 9.0
    assert by_id["MAT-2"] == 20.0  # sin cambios


def test_apply_production_appends_to_existing_movements():
    inventory = [_material("MAT-1", 1.0, 1.0, available_quantity=10.0)]
    product = {"name": "Producto", "recipe": [{"item_id": "MAT-1", "quantity": 1.0}]}
    existing_movement = {"movement_id": "OLD-1"}

    _, movements = catalog._apply_production(product, quantity=1.0, inventory=inventory, movements=[existing_movement])

    assert len(movements) == 2
    assert movements[0] == existing_movement
