"""Pruebas de gastos y presupuesto mensual (`src/expenses_budget.py`)."""

from __future__ import annotations

from src import expenses_budget as eb


def test_month_extracts_year_month_prefix():
    assert eb._month("2026-07-15") == "2026-07"


def test_month_returns_empty_for_short_string():
    assert eb._month("2026") == ""


def test_month_returns_empty_for_empty_string():
    assert eb._month("") == ""


def test_budget_finds_matching_category_and_month():
    budgets = [{"category": "Internet", "month": "2026-07", "amount": 50.0}]
    assert eb._budget("Internet", "2026-07", budgets) == 50.0


def test_budget_returns_zero_when_no_match():
    budgets = [{"category": "Internet", "month": "2026-07", "amount": 50.0}]
    assert eb._budget("Internet", "2026-08", budgets) == 0.0
    assert eb._budget("Electricidad", "2026-07", budgets) == 0.0


def test_budget_returns_zero_with_no_budgets():
    assert eb._budget("Internet", "2026-07", budgets=[]) == 0.0


def test_categories_and_methods_are_defined():
    assert "Internet" in eb.CATEGORIES
    assert "Efectivo" in eb.METHODS
