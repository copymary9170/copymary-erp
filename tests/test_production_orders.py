"""Pruebas de órdenes de producción (`src/production_orders.py`)."""

from __future__ import annotations

from datetime import date, timedelta

from src import production_orders as po


def test_num_parses_comma_as_decimal_separator():
    """Formato usado en Venezuela/LatAm: coma como separador decimal."""
    assert po._num("12,5") == 12.5


def test_num_returns_default_for_invalid_value():
    assert po._num("no-es-numero", default=1.0) == 1.0


def test_order_cost_multiplies_unit_cost_by_quantity():
    order = {"estimated_unit_cost": 3.5, "quantity": 10}
    assert po._order_cost(order) == 35.0


def test_order_price_multiplies_unit_price_by_quantity():
    order = {"estimated_unit_price": 5.0, "quantity": 10}
    assert po._order_price(order) == 50.0


def test_order_cost_defaults_quantity_to_one_when_missing():
    order = {"estimated_unit_cost": 7.0}
    assert po._order_cost(order) == 7.0


def test_open_orders_excludes_delivered_and_cancelled():
    orders = [
        {"order_id": "OP-1", "status": "Pendiente"},
        {"order_id": "OP-2", "status": "En producción"},
        {"order_id": "OP-3", "status": "Entregada"},
        {"order_id": "OP-4", "status": "Cancelada"},
    ]
    open_ids = {row["order_id"] for row in po._open_orders(orders)}
    assert open_ids == {"OP-1", "OP-2"}


def test_late_orders_only_includes_open_orders_past_due_date():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    orders = [
        {"order_id": "OP-1", "status": "En producción", "due_date": yesterday},  # atrasada
        {"order_id": "OP-2", "status": "En producción", "due_date": tomorrow},   # a tiempo
        {"order_id": "OP-3", "status": "Entregada", "due_date": yesterday},      # ya entregada, no cuenta
    ]
    late_ids = {row["order_id"] for row in po._late_orders(orders)}
    assert late_ids == {"OP-1"}


def test_status_flow_defines_valid_transitions_only():
    assert "Cancelada" in po.STATUS_FLOW["Pendiente"]
    assert po.STATUS_FLOW["Entregada"] == ()
    assert po.STATUS_FLOW["Cancelada"] == ()
