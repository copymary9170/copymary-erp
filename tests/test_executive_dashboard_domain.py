from datetime import date

import pytest

from src.executive_dashboard_domain import (
    approval_trace,
    break_even,
    capacity_usage,
    delivery_performance,
    net_margin,
    product_profitability,
    sales_period_comparison,
    top_customers,
    waste_by_process,
)
from src.executive_dashboard_integration import canonical_area_for_page


def test_financial_kpis_match_expected_values():
    sales = [
        {"description": "Copias", "total": 100, "estimated_cost": 40, "quantity": 10, "client_id": "C1", "created_at_utc": "2026-07-10"},
        {"description": "Copias", "total": 50, "estimated_cost": 20, "quantity": 5, "client_id": "C1", "created_at_utc": "2026-06-10"},
        {"description": "Diseño", "total": 80, "estimated_cost": 30, "quantity": 1, "client_id": "C2", "created_at_utc": "2026-07-12"},
    ]
    profitability = product_profitability(sales)
    copies = next(row for row in profitability if row["product"] == "Copias")
    assert copies["revenue"] == 150
    assert copies["profit"] == 90
    assert copies["margin_pct"] == pytest.approx(60)

    margin = net_margin(sales, operating_expenses=20)
    assert margin["net_profit"] == 120
    assert margin["net_margin_pct"] == pytest.approx(120 / 230 * 100)

    point = break_even(1000, 40)
    assert point["sales_required"] == 2500


def test_top_customers_and_period_comparison():
    sales = [
        {"client_id": "C1", "total": 200, "created_at_utc": "2026-07-20"},
        {"client_id": "C2", "total": 100, "created_at_utc": "2026-06-20"},
    ]
    customers = [{"client_id": "C1", "name": "Ana"}, {"client_id": "C2", "name": "Luis"}]
    assert top_customers(sales, customers)[0]["customer"] == "Ana"
    comparison = sales_period_comparison(
        sales,
        date(2026, 7, 1), date(2026, 7, 31),
        date(2026, 6, 1), date(2026, 6, 30),
    )
    assert comparison == {"current": 200, "previous": 100, "variation": 100, "variation_pct": 100}


def test_operational_kpis_match_expected_values():
    orders = [
        {"promised_date": "2026-07-10", "delivered_at": "2026-07-09", "used_minutes": 60, "available_minutes": 120},
        {"promised_date": "2026-07-10", "delivered_at": "2026-07-12", "used_minutes": 30, "available_minutes": 60},
        {"promised_date": "2026-07-15", "used_minutes": 10, "available_minutes": 20},
    ]
    delivery = delivery_performance(orders, date(2026, 7, 14))
    assert delivery["on_time"] == 1
    assert delivery["late"] == 1
    assert delivery["pending"] == 1
    assert delivery["on_time_pct"] == 50

    capacity = capacity_usage(orders)
    assert capacity["used_minutes"] == 100
    assert capacity["available_minutes"] == 200
    assert capacity["usage_pct"] == 50

    waste = waste_by_process([
        {"process": "Corte", "input_quantity": 100, "waste_quantity": 5},
        {"process": "Corte", "input_quantity": 100, "waste_quantity": 3},
    ])
    assert waste[0]["waste"] == 8
    assert waste[0]["waste_pct"] == 4


def test_approval_trace_normalizes_actor_and_entity():
    rows = approval_trace([
        {"purchase_id": "P1", "approved_by": "María", "approved_at_utc": "2026-07-01", "approval_status": "Aprobado"},
        {"price_change_id": "PC1", "changed_by": "Ana", "changed_at_utc": "2026-07-02", "status": "Aplicado"},
    ])
    assert rows[0]["approved_by"] == "Ana"
    assert {row["entity_id"] for row in rows} == {"P1", "PC1"}


def test_navigation_resolves_page_to_canonical_area():
    groups = {
        "Inicio": ("Inicio", "Panel comercial"),
        "Finanzas y tesorería": ("Panel financiero y cierres", "Caja"),
    }
    assert canonical_area_for_page("Panel comercial", groups) == "Inicio"
    assert canonical_area_for_page("Panel financiero y cierres", groups) == "Finanzas y tesorería"
    assert canonical_area_for_page("No existe", groups) is None
