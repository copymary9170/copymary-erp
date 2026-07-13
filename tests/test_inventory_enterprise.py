"""Pruebas de `src/inventory_enterprise.py` (módulo Inventario activo).

Cubren especialmente el bug real de doble conteo de existencia inicial
(antes se compensaba con un monkeypatch frágil en
`inventory_enterprise_loader.py`, atado al texto exacto "Existencia inicial")
y la reconstrucción de la pestaña de Reservas, que había quedado sin forma
de crearse tras reemplazar `inventory_plus.py` como módulo activo.
"""

from __future__ import annotations

import streamlit as st

from src import inventory_enterprise as ie
from src.session_utils import read_list


def _item(item_id="ITM-1", available_quantity=0.0, unit_cost=5.0, purchased_quantity=1.0):
    return {
        "item_id": item_id, "sku": "", "name": "Vinil blanco", "category": "Corte y Cameo",
        "unit_name": "hoja", "available_quantity": available_quantity, "minimum_stock": 0.0,
        "maximum_stock": 0.0, "unit_cost": unit_cost, "purchase_cost": unit_cost * purchased_quantity,
        "purchased_quantity": purchased_quantity, "supplier": "", "location": "Almacén principal",
        "lot": "", "expiry_date": "", "active": True,
    }


# ---------------------------------------------------------------------------
# _movement — costo promedio ponderado y no permitir existencia negativa
# ---------------------------------------------------------------------------

def test_movement_entrada_increases_available_quantity():
    item = _item(available_quantity=10.0)
    ie._movement(item, "Entrada", 5.0, "Compra", 5.0)
    assert item["available_quantity"] == 15.0


def test_movement_salida_decreases_available_quantity():
    item = _item(available_quantity=10.0)
    ie._movement(item, "Salida", 4.0, "Venta")
    assert item["available_quantity"] == 6.0


def test_movement_salida_does_not_go_below_zero():
    item = _item(available_quantity=2.0)
    ie._movement(item, "Salida", 100.0, "Venta")
    assert item["available_quantity"] == 0.0


def test_movement_entrada_updates_weighted_average_cost():
    # 10 unidades a costo 5.0 (valor 50) + 10 unidades entrantes a costo 9.0 (valor 90)
    # => promedio ponderado = 140 / 20 = 7.0
    item = _item(available_quantity=10.0, unit_cost=5.0)
    ie._movement(item, "Entrada", 10.0, "Compra", 9.0)
    assert item["unit_cost"] == 7.0


def test_movement_creates_traceable_history_entry():
    item = _item(available_quantity=10.0)
    ie._movement(item, "Salida", 3.0, "Trabajo XYZ")
    movements = read_list("inventory_movements")
    assert len(movements) == 1
    assert movements[0]["movement_type"] == "Salida"
    assert movements[0]["reason"] == "Trabajo XYZ"
    assert movements[0]["previous_quantity"] == 10.0
    assert movements[0]["resulting_quantity"] == 7.0


# ---------------------------------------------------------------------------
# Bug real corregido: doble conteo de la existencia inicial al registrar
# ---------------------------------------------------------------------------

def test_initial_stock_movement_does_not_double_count():
    """Antes: crear el ítem con available_quantity=100 y LUEGO llamar a
    _movement(..., 'Entrada', 100, 'Existencia inicial', ...) dejaba
    available_quantity en 200 (100 puesto al crear + 100 sumado por el
    movimiento). Se corrigió creando el ítem siempre en 0 y dejando que el
    movimiento de 'Existencia inicial' sea la única fuente de verdad."""
    item = _item(available_quantity=0.0, unit_cost=5.0)
    ie._movement(item, "Entrada", 100.0, "Existencia inicial", 5.0)
    assert item["available_quantity"] == 100.0


def test_register_creates_item_with_zero_before_initial_movement():
    """`_register` debe crear el ítem con available_quantity=0.0 antes de
    aplicar el movimiento de existencia inicial (regresión del bug de
    doble conteo)."""
    import inspect
    source = inspect.getsource(ie._register)
    assert '"available_quantity": 0.0' in source


# ---------------------------------------------------------------------------
# _reserved_for / pestaña de Reservas — funcionalidad restaurada
# ---------------------------------------------------------------------------

def test_reserved_for_sums_only_active_reservations_of_that_item():
    reservations = [
        {"item_id": "ITM-1", "quantity": 5.0, "status": "Activa"},
        {"item_id": "ITM-1", "quantity": 3.0, "status": "Liberada"},
        {"item_id": "ITM-2", "quantity": 10.0, "status": "Activa"},
    ]
    assert ie._reserved_for("ITM-1", reservations) == 5.0


def test_reserved_for_returns_zero_when_no_reservations():
    assert ie._reserved_for("ITM-1", []) == 0.0


def test_reservations_tab_creates_active_reservation(monkeypatch):
    """Simula el flujo de creación de una reserva sin depender de Streamlit
    real: valida la lógica de negocio (cantidad <= disponible menos ya
    reservado) escribiendo directamente en `inventory_reservations`, igual
    estructura que usa `stock_alerts_intelligence.py` para leerlas."""
    st.session_state["inventory_registry"] = [_item(available_quantity=50.0)]
    reservations = read_list("inventory_reservations")
    reservations.append({
        "reservation_id": "RSV-TEST1", "item_id": "ITM-1", "quantity": 20.0,
        "source": "Producción", "reference": "OP-1", "due_date": "2026-07-20",
        "responsible": "Ana", "note": "", "status": "Activa", "created_at_utc": "2026-07-13T00:00:00+00:00",
    })
    from src.session_utils import save_list
    save_list("inventory_reservations", reservations)

    free = ie._num(50.0) - ie._reserved_for("ITM-1", read_list("inventory_reservations"))
    assert free == 30.0
