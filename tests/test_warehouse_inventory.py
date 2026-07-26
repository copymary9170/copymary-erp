from datetime import date
from decimal import Decimal

import pytest

from src.warehouse_inventory import (
    StockMovement,
    build_kardex,
    build_transfer,
    ensure_lot_dispatchable,
    ensure_not_duplicate_receipt,
    ensure_receipt_source,
    total_stock,
    validate_transfer,
    warehouse_stock,
)


def movement(mid, qty, cost="0", warehouse="MAIN", source="", reference=""):
    return StockMovement(
        movement_id=mid,
        item_id="PAPEL",
        warehouse_id=warehouse,
        movement_date=date(2026, 7, 1),
        quantity=Decimal(str(qty)),
        unit_cost=Decimal(str(cost)),
        source_module=source,
        reference=reference,
    )


def test_transfer_preserves_total_stock_and_balances_warehouses():
    existing = [movement("OPEN", 20, "2.00", "MAIN")]
    outgoing, incoming = build_transfer(
        transfer_id="TR-1", item_id="PAPEL", origin_warehouse_id="MAIN",
        destination_warehouse_id="SHOP", quantity=7, unit_cost="2.00",
        movement_date=date(2026, 7, 2),
    )
    validate_transfer(existing, outgoing, incoming)
    after = existing + [outgoing, incoming]
    assert total_stock(after, "PAPEL") == Decimal("20.0000")
    assert warehouse_stock(after, "PAPEL", "MAIN") == Decimal("13.0000")
    assert warehouse_stock(after, "PAPEL", "SHOP") == Decimal("7.0000")


def test_transfer_rejects_insufficient_origin_stock():
    existing = [movement("OPEN", 2, "2.00", "MAIN")]
    outgoing, incoming = build_transfer(
        transfer_id="TR-2", item_id="PAPEL", origin_warehouse_id="MAIN",
        destination_warehouse_id="SHOP", quantity=3, unit_cost="2.00",
        movement_date=date(2026, 7, 2),
    )
    with pytest.raises(ValueError, match="insuficiente"):
        validate_transfer(existing, outgoing, incoming)


def test_kardex_matches_movements_and_weighted_average():
    rows = build_kardex([
        movement("E1", 10, "2.00"),
        StockMovement("E2", "PAPEL", "MAIN", date(2026, 7, 2), Decimal("10"), Decimal("4.00")),
        StockMovement("S1", "PAPEL", "MAIN", date(2026, 7, 3), Decimal("-5")),
    ], "PAPEL", "MAIN")
    assert rows[-1].balance_qty == Decimal("15.0000")
    assert rows[-1].average_cost == Decimal("3.00")
    assert rows[-1].balance_value == Decimal("45.00")
    assert sum(row.entry_qty - row.exit_qty for row in rows) == rows[-1].balance_qty


def test_expired_lot_cannot_be_dispatched():
    with pytest.raises(ValueError, match="vencido"):
        ensure_lot_dispatchable(date(2026, 7, 1), date(2026, 7, 26))


def test_valid_lot_can_be_dispatched():
    ensure_lot_dispatchable(date(2026, 8, 1), date(2026, 7, 26))


def test_purchase_entry_only_accepts_goods_receipt():
    ensure_receipt_source("goods_receipt")
    with pytest.raises(ValueError, match="goods_receipt"):
        ensure_receipt_source("purchases_plus")


def test_duplicate_goods_receipt_is_rejected():
    existing = [movement("GR-1", 5, "2.00", source="goods_receipt", reference="REC-10")]
    with pytest.raises(ValueError, match="ya fue aplicada"):
        ensure_not_duplicate_receipt(existing, "REC-10", "PAPEL")
