"""Pruebas de comisiones de equipo (`src/team_commissions.py`)."""

from __future__ import annotations

from src import team_commissions as tc


def test_member_name_found():
    members = [{"member_id": "M-1", "name": "Ana"}]
    assert tc._member_name("M-1", members) == "Ana"


def test_member_name_not_found_returns_placeholder():
    assert tc._member_name("NO-EXISTE", members=[]) == "Colaborador no disponible"


def test_earned_for_percentage_mode_only_counts_paid_non_cancelled_sales():
    member = {"commission_mode": "Porcentaje", "commission_value": 10.0}
    sales = [
        {"total": 100.0, "payment_status": "Pagado", "order_status": "Entregado"},
        {"total": 100.0, "payment_status": "Pendiente", "order_status": "Entregado"},  # no pagada, no cuenta
        {"total": 100.0, "payment_status": "Pagado", "order_status": "Cancelado"},  # cancelada, no cuenta
    ]
    # Solo la primera venta cuenta: 100 * 10% = 10.0
    assert tc._earned_for(member, sales) == 10.0


def test_earned_for_fixed_amount_mode_counts_per_paid_sale():
    member = {"commission_mode": "Monto por venta", "commission_value": 5.0}
    sales = [
        {"total": 999.0, "payment_status": "Pagado", "order_status": "Entregado"},
        {"total": 999.0, "payment_status": "Pagado", "order_status": "Entregado"},
    ]
    # 2 ventas pagadas * $5 fijo = 10.0 (el total de la venta no afecta el monto fijo)
    assert tc._earned_for(member, sales) == 10.0


def test_earned_for_with_no_sales_is_zero():
    member = {"commission_mode": "Porcentaje", "commission_value": 10.0}
    assert tc._earned_for(member, sales=[]) == 0.0


def test_paid_to_sums_only_payments_for_that_member():
    payments = [
        {"member_id": "M-1", "amount": 20.0},
        {"member_id": "M-2", "amount": 999.0},
        {"member_id": "M-1", "amount": 5.0},
    ]
    assert tc._paid_to("M-1", payments) == 25.0


def test_paid_to_with_no_payments_is_zero():
    assert tc._paid_to("M-1", payments=[]) == 0.0
