"""Pruebas de reapertura de cierres de caja (`src/cash_closing_reopen.py`)."""

from __future__ import annotations

from src import cash_closing_reopen as reopen
from src import financial_control


def test_active_closings_excludes_reopened():
    closings = [
        {"closing_id": "C-1", "reopened": False},
        {"closing_id": "C-2", "reopened": True},
    ]
    active_ids = {row["closing_id"] for row in reopen._active_closings(closings)}
    assert active_ids == {"C-1"}


def test_closed_ids_collects_movement_ids_from_active_closings_only():
    closings = [
        {"closing_id": "C-1", "reopened": False, "movement_ids": ["M-1", "M-2"]},
        {"closing_id": "C-2", "reopened": True, "movement_ids": ["M-3"]},  # reabierto, no cuenta
    ]
    assert reopen._closed_ids(closings) == {"M-1", "M-2"}


def test_closed_ids_empty_when_no_closings():
    assert reopen._closed_ids([]) == set()


def test_opening_by_method_reads_counted_amounts_from_active_closings():
    closings = [
        {"closing_id": "C-1", "reopened": False, "counted_by_method": {"Efectivo": 100.0, "Zelle": 50.0}},
    ]
    opening = reopen._opening_by_method(closings)
    assert opening["Efectivo"] == 100.0
    assert opening["Zelle"] == 50.0
    # Métodos sin conteo explícito quedan en 0.
    assert opening["Transferencia"] == 0.0


def test_opening_by_method_ignores_reopened_closings():
    closings = [{"closing_id": "C-1", "reopened": True, "counted_by_method": {"Efectivo": 999.0}}]
    opening = reopen._opening_by_method(closings)
    assert opening["Efectivo"] == 0.0


def test_opening_by_method_covers_all_known_payment_methods():
    opening = reopen._opening_by_method([])
    assert set(opening.keys()) == set(financial_control.METHODS)
