"""Pruebas del motor de costeo por procesos / BOM (`src/bom_costing.py`).

`_material_unit_cost` y `_step_total` son puras (reciben dicts). `_recipe_total`
lee de la base de datos, así que esas pruebas insertan filas directamente con
`erp_database.connect()` sobre la base SQLite temporal de la prueba.
"""

from __future__ import annotations

from src import bom_costing, erp_database as db


# ---------------------------------------------------------------------------
# _material_unit_cost
# ---------------------------------------------------------------------------

def test_material_unit_cost_uses_color_cost_by_default():
    material = {"unit_cost": 1.0, "unit_cost_color": 2.0, "unit_cost_bw": 0.5}
    assert bom_costing._material_unit_cost(material, "color") == 2.0


def test_material_unit_cost_uses_bw_cost_when_requested():
    material = {"unit_cost": 1.0, "unit_cost_color": 2.0, "unit_cost_bw": 0.5}
    assert bom_costing._material_unit_cost(material, "bn") == 0.5


def test_material_unit_cost_falls_back_to_legacy_cost_when_color_missing():
    """Materiales cargados antes de la migración v2 no tienen unit_cost_color/bw."""
    material = {"unit_cost": 1.5, "unit_cost_color": None, "unit_cost_bw": None}
    assert bom_costing._material_unit_cost(material, "color") == 1.5
    assert bom_costing._material_unit_cost(material, "bn") == 1.5


# ---------------------------------------------------------------------------
# resale_price
# ---------------------------------------------------------------------------

def test_resale_price_applies_margin_to_base_cost():
    material = {"use_type": "reventa", "unit_cost": 10.0, "resale_margin_percent": 25.0}
    assert bom_costing.resale_price(material) == 12.5


def test_resale_price_zero_for_insumo_materials():
    """Un material puramente insumo no se vende directo, no tiene precio de reventa."""
    material = {"use_type": "insumo", "unit_cost": 10.0, "resale_margin_percent": 25.0}
    assert bom_costing.resale_price(material) == 0.0


def test_resale_price_applies_to_mixto_use_type_too():
    material = {"use_type": "mixto", "unit_cost": 20.0, "resale_margin_percent": 10.0}
    assert bom_costing.resale_price(material) == 22.0


def test_resale_price_zero_margin_equals_base_cost():
    material = {"use_type": "reventa", "unit_cost": 10.0, "resale_margin_percent": 0.0}
    assert bom_costing.resale_price(material) == 10.0


# ---------------------------------------------------------------------------
# suggested_pieces_per_sheet (estimación de anidado por área)
# ---------------------------------------------------------------------------

def test_suggested_pieces_per_sheet_divides_areas():
    # Hoja de 900 cm², diseño de 100 cm² -> caben 9 piezas.
    assert bom_costing.suggested_pieces_per_sheet(design_area_cm2=100.0, sheet_area_cm2=900.0) == 9


def test_suggested_pieces_per_sheet_rounds_down():
    # 900 / 400 = 2.25 -> se redondea hacia abajo, no se asume que cabe una pieza parcial.
    assert bom_costing.suggested_pieces_per_sheet(design_area_cm2=400.0, sheet_area_cm2=900.0) == 2


def test_suggested_pieces_per_sheet_has_floor_of_one():
    # Un diseño más grande que la hoja no debe dar 0 (evita división en costo por cero piezas).
    assert bom_costing.suggested_pieces_per_sheet(design_area_cm2=1000.0, sheet_area_cm2=100.0) == 1


def test_suggested_pieces_per_sheet_defaults_to_one_without_area_data():
    assert bom_costing.suggested_pieces_per_sheet(design_area_cm2=0.0, sheet_area_cm2=0.0) == 1
    assert bom_costing.suggested_pieces_per_sheet(design_area_cm2=100.0, sheet_area_cm2=0.0) == 1


# ---------------------------------------------------------------------------
# _step_total
# ---------------------------------------------------------------------------

def test_step_total_material_cost_includes_waste_and_pieces_per_sheet():
    materials = {"MAT-1": {"unit_cost_color": 10.0, "waste_percent": 10.0}}
    step = {
        "material_id": "MAT-1",
        "material_quantity": 1.0,
        "print_mode": "color",
        "pieces_per_sheet": 2.0,
    }
    result = bom_costing._step_total(step, materials, machines={}, consumables=[])
    # (1.0 * 10.0 * 1.10) / 2 piezas por hoja = 5.5
    assert result["material"] == 5.5
    assert result["total"] == 5.5


def test_step_total_machine_cost_uses_depreciation_plus_maintenance():
    machines = {
        "MCH-1": {
            "acquisition_cost": 6000.0,
            "useful_life_hours": 1000.0,
            "maintenance_cost_per_hour": 0.5,
            "power_kw": 0.0,
        }
    }
    step = {"machine_id": "MCH-1", "machine_minutes": 60.0}
    result = bom_costing._step_total(step, materials={}, machines=machines, consumables=[])
    # 1 hora * (6000/1000 depreciación + 0.5 mantenimiento) = 6.5
    assert result["machine"] == 6.5


def test_step_total_includes_active_consumables_for_the_machine():
    machines = {"MCH-1": {"acquisition_cost": 0.0, "useful_life_hours": 1.0, "maintenance_cost_per_hour": 0.0, "power_kw": 0.0}}
    consumables = [
        {"machine_id": "MCH-1", "replacement_cost": 100.0, "useful_life_units": 50.0, "active": 1},
        {"machine_id": "MCH-1", "replacement_cost": 999.0, "useful_life_units": 1.0, "active": 0},  # inactivo, no cuenta
        {"machine_id": "OTHER", "replacement_cost": 999.0, "useful_life_units": 1.0, "active": 1},  # otra máquina, no cuenta
    ]
    step = {"machine_id": "MCH-1", "machine_minutes": 0.0}
    result = bom_costing._step_total(step, materials={}, machines=machines, consumables=consumables)
    assert result["consumable"] == 2.0  # 100 / 50


def test_step_total_labor_cost_converts_minutes_to_hours():
    step = {"labor_minutes": 30.0, "labor_rate_per_hour": 10.0}
    result = bom_costing._step_total(step, materials={}, machines={}, consumables=[])
    assert result["labor"] == 5.0


def test_step_total_with_no_material_or_machine_is_zero():
    result = bom_costing._step_total({}, materials={}, machines={}, consumables=[])
    assert result["total"] == 0.0


# ---------------------------------------------------------------------------
# _recipe_total (integra con la base de datos)
# ---------------------------------------------------------------------------

def _insert_material(material_id: str, unit_cost_color: float) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO production_materials(material_id, name, category, unit, unit_cost, currency, unit_cost_color, created_at_utc)
            VALUES (?, 'Material de prueba', 'insumo', 'unidad', ?, 'USD', ?, ?)
            """,
            (material_id, unit_cost_color, unit_cost_color, db._now()),
        )


def _insert_recipe_step(recipe_id: str, step_order: int, material_id: str, quantity: float) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO recipe_steps(step_id, recipe_id, step_order, process_type, material_id, material_quantity, created_at_utc)
            VALUES (?, ?, ?, 'Impresión', ?, ?, ?)
            """,
            (f"STEP-{recipe_id}-{step_order}", recipe_id, step_order, material_id, quantity, db._now()),
        )


def test_recipe_total_sums_all_steps_in_order(isolated_database):
    db.initialize_database()
    _insert_material("MAT-A", unit_cost_color=2.0)
    _insert_material("MAT-B", unit_cost_color=3.0)
    _insert_recipe_step("REC-1", step_order=1, material_id="MAT-A", quantity=1.0)
    _insert_recipe_step("REC-1", step_order=2, material_id="MAT-B", quantity=1.0)

    total, details = bom_costing._recipe_total("REC-1")

    assert total == 5.0
    assert len(details) == 2


def test_recipe_total_ignores_steps_from_other_recipes(isolated_database):
    db.initialize_database()
    _insert_material("MAT-A", unit_cost_color=2.0)
    _insert_recipe_step("REC-1", step_order=1, material_id="MAT-A", quantity=1.0)
    _insert_recipe_step("REC-OTHER", step_order=1, material_id="MAT-A", quantity=100.0)

    total, _ = bom_costing._recipe_total("REC-1")
    assert total == 2.0


# ---------------------------------------------------------------------------
# _accumulate_machine_usage_from_job — un trabajo real confirmado alimenta el
# contador de uso de Mantenimiento preventivo, sin actualizarlo a mano.
# ---------------------------------------------------------------------------

def _insert_machine_step(recipe_id: str, step_order: int, machine_id: str, machine_minutes: float) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO recipe_steps(step_id, recipe_id, step_order, process_type, machine_id, machine_minutes, created_at_utc)
            VALUES (?, ?, ?, 'Sublimación', ?, ?, ?)
            """,
            (f"STEP-{recipe_id}-{step_order}", recipe_id, step_order, machine_id, machine_minutes, db._now()),
        )


def test_accumulate_machine_usage_feeds_hours_into_maintenance_plan(isolated_database):
    from src import machine_maintenance as mm

    db.initialize_database()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO production_machines(machine_id, name, category, acquisition_cost, useful_life_hours, power_kw, maintenance_cost_per_hour, active, created_at_utc) VALUES ('MAC-1', 'Prensa', 'Sublimación', 300, 5000, 0.5, 0.1, 1, '2026-01-01')"
        )
    plan_id = mm.create_plan("MAC-1", "Revisar presión", frequency_days=0, usage_metric="Horas de uso", usage_frequency=100.0, current_usage=0.0)
    _insert_machine_step("REC-1", step_order=1, machine_id="MAC-1", machine_minutes=30.0)

    # 30 minutos por unidad * 4 unidades = 120 min = 2 horas
    bom_costing._accumulate_machine_usage_from_job("REC-1", quantity=4.0)

    plan = next(p for p in mm.list_plans() if p["plan_id"] == plan_id)
    assert plan["current_usage"] == 2.0


def test_accumulate_machine_usage_ignores_steps_without_machine(isolated_database):
    db.initialize_database()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO recipe_steps(step_id, recipe_id, step_order, process_type, created_at_utc) VALUES ('STEP-X', 'REC-2', 1, 'Impresión', ?)",
            (db._now(),),
        )
    # No debe lanzar excepción aunque el paso no tenga máquina ni minutos.
    bom_costing._accumulate_machine_usage_from_job("REC-2", quantity=3.0)
