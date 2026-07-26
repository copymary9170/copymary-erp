from __future__ import annotations

from src.business_goals_admin_closure import calculate_progress, calculated_status


def _goal(*, target: float = 100.0, kpi_code: str = "monthly_sales") -> dict:
    return {"target_value": target, "kpi_code": kpi_code}


def test_higher_is_better_progress():
    assert calculate_progress(_goal(target=200), 150) == 75.0
    assert calculated_status(75.0) == "En curso"


def test_lower_is_better_progress():
    goal = _goal(target=500, kpi_code="overdue_receivables_limit")
    assert calculate_progress(goal, 250) == 100.0
    assert calculate_progress(goal, 1000) == 50.0


def test_status_bands_are_deterministic():
    assert calculated_status(100) == "Cumplido"
    assert calculated_status(80) == "En curso"
    assert calculated_status(60) == "En riesgo"
    assert calculated_status(20) == "Crítico"


def test_unknown_kpi_has_zero_progress():
    assert calculate_progress(_goal(kpi_code="unknown"), 100) == 0.0
