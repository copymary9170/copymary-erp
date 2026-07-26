from datetime import date
from decimal import Decimal

import pytest

from src.commercial_domain import (
    CommercialDocument,
    CommercialLine,
    DiscountPolicy,
    authorize_discount,
    convert_document,
    customer_360,
    segment_customers,
    transition_crm,
    validate_conversion,
)


def _quote() -> CommercialDocument:
    return CommercialDocument(
        document_id="Q-001",
        document_type="quote",
        customer_id="C-001",
        currency="USD",
        exchange_rate=Decimal("40.00"),
        lines=(
            CommercialLine("Impresión", Decimal("2"), Decimal("10.00"), Decimal("1.00")),
            CommercialLine("Diseño", Decimal("1"), Decimal("5.00")),
        ),
        tax_amount=Decimal("3.84"),
        other_charges=Decimal("1.00"),
        status="approved",
    )


def test_quote_to_order_and_invoice_preserve_amounts():
    quote = _quote()
    order = convert_document(quote, "order", "O-001")
    invoice = convert_document(order, "invoice", "F-001")

    validate_conversion(quote, order)
    validate_conversion(order, invoice)
    assert order.subtotal == quote.subtotal
    assert order.total == quote.total
    assert invoice.total == quote.total
    assert invoice.lines == quote.lines
    assert invoice.exchange_rate == quote.exchange_rate


def test_discount_over_automatic_limit_requires_approval():
    policy = DiscountPolicy(Decimal("10"), Decimal("25"))
    with pytest.raises(PermissionError):
        authorize_discount(Decimal("100"), Decimal("15"), policy)
    result = authorize_discount(Decimal("100"), Decimal("15"), policy, approved_by="GER-1")
    assert result["requires_approval"] is True
    assert result["approved_by"] == "GER-1"


def test_discount_cannot_exceed_absolute_limit():
    policy = DiscountPolicy(Decimal("10"), Decimal("25"))
    with pytest.raises(ValueError):
        authorize_discount(100, 30, policy, approved_by="GER-1")


def test_crm_pipeline_accepts_valid_transitions():
    state = "lead"
    for target in ("qualified", "opportunity", "quoted", "won"):
        state = transition_crm(state, target)
    assert state == "won"


def test_crm_pipeline_rejects_invalid_transition():
    with pytest.raises(ValueError):
        transition_crm("lead", "won")


def _customers_and_sales():
    customers = [
        {"client_id": "A", "name": "Ana", "birthday": "1990-07-10", "preferences": ["fotográfico"]},
        {"client_id": "B", "name": "Bea", "birthday": "1992-03-20"},
        {"client_id": "C", "name": "Carla"},
    ]
    sales = [
        {"client_id": "A", "total": 10, "payment_status": "Pagado", "created_at_utc": "2026-07-20T10:00:00"},
        {"client_id": "A", "total": 15, "payment_status": "Pagado", "created_at_utc": "2026-07-10T10:00:00"},
        {"client_id": "A", "total": 20, "payment_status": "Pendiente", "created_at_utc": "2026-06-20T10:00:00"},
        {"client_id": "B", "total": 8, "payment_status": "Pagado", "created_at_utc": "2025-12-01T10:00:00"},
    ]
    return customers, sales


def test_customer_360_builds_balance_history_and_preferences():
    customers, sales = _customers_and_sales()
    profile = customer_360(customers[0], sales, as_of=date(2026, 7, 26))
    assert profile["purchase_count"] == 3
    assert profile["total_purchases"] == Decimal("45.00")
    assert profile["outstanding_balance"] == Decimal("20.00")
    assert profile["preferences"] == ["fotográfico"]
    assert len(profile["last_orders"]) == 3


def test_segmentation_filters_correctly():
    customers, sales = _customers_and_sales()
    as_of = date(2026, 7, 26)
    assert [row["customer_id"] for row in segment_customers(customers, sales, "active", as_of)] == ["A"]
    assert {row["customer_id"] for row in segment_customers(customers, sales, "inactive", as_of)} == {"B", "C"}
    assert [row["customer_id"] for row in segment_customers(customers, sales, "debtors", as_of)] == ["A"]
    assert [row["customer_id"] for row in segment_customers(customers, sales, "frequent", as_of)] == ["A"]
    assert [row["customer_id"] for row in segment_customers(customers, sales, "birthday_month", as_of)] == ["A"]
