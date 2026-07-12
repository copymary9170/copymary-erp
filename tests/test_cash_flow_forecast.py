"""Pruebas del flujo de caja proyectado (`src/cash_flow_forecast.py`)."""

from __future__ import annotations

from datetime import date, timedelta

from src import cash_flow_forecast as cf

TODAY = date(2026, 7, 11)


# ---------------------------------------------------------------------------
# current_cash_position
# ---------------------------------------------------------------------------

def test_current_cash_position_subtracts_expenses_from_income():
    movements = [{"movement_type": "Ingreso", "amount": 5000.0}, {"movement_type": "Egreso", "amount": 2000.0}]
    assert cf.current_cash_position(movements) == 3000.0


def test_current_cash_position_can_be_negative():
    movements = [{"movement_type": "Ingreso", "amount": 100.0}, {"movement_type": "Egreso", "amount": 500.0}]
    assert cf.current_cash_position(movements) == -400.0


def test_current_cash_position_with_no_movements_is_zero():
    assert cf.current_cash_position([]) == 0.0


# ---------------------------------------------------------------------------
# expected_receivables
# ---------------------------------------------------------------------------

def test_expected_receivables_includes_balance_due_within_horizon():
    sales = [{"sale_id": "S1", "total": 1000.0}]
    metadata = [{"sale_id": "S1", "due_date": (TODAY + timedelta(days=20)).isoformat()}]
    assert cf.expected_receivables(sales, [], metadata, TODAY, 30) == 1000.0


def test_expected_receivables_excludes_due_date_beyond_horizon():
    sales = [{"sale_id": "S1", "total": 1000.0}]
    metadata = [{"sale_id": "S1", "due_date": (TODAY + timedelta(days=40)).isoformat()}]
    assert cf.expected_receivables(sales, [], metadata, TODAY, 30) == 0.0


def test_expected_receivables_includes_overdue_accounts():
    """Una cuenta ya vencida sigue siendo dinero que se espera cobrar."""
    sales = [{"sale_id": "S1", "total": 500.0}]
    metadata = [{"sale_id": "S1", "due_date": (TODAY - timedelta(days=10)).isoformat()}]
    assert cf.expected_receivables(sales, [], metadata, TODAY, 30) == 500.0


def test_expected_receivables_subtracts_payments_already_received():
    sales = [{"sale_id": "S1", "total": 1000.0}]
    payments = [{"sale_id": "S1", "amount": 400.0}]
    metadata = [{"sale_id": "S1", "due_date": (TODAY + timedelta(days=5)).isoformat()}]
    assert cf.expected_receivables(sales, payments, metadata, TODAY, 30) == 600.0


def test_expected_receivables_skips_sales_without_due_date():
    sales = [{"sale_id": "S1", "total": 1000.0}]
    assert cf.expected_receivables(sales, [], metadata=[], as_of=TODAY, horizon_days=30) == 0.0


def test_expected_receivables_ignores_invalid_due_date():
    sales = [{"sale_id": "S1", "total": 1000.0}]
    metadata = [{"sale_id": "S1", "due_date": "fecha-invalida"}]
    assert cf.expected_receivables(sales, [], metadata, TODAY, 30) == 0.0


# ---------------------------------------------------------------------------
# expected_payables
# ---------------------------------------------------------------------------

def test_expected_payables_includes_balance_due_within_horizon():
    purchases = [{"purchase_id": "P1", "total": 300.0}]
    metadata = [{"purchase_id": "P1", "due_date": (TODAY + timedelta(days=5)).isoformat()}]
    assert cf.expected_payables(purchases, [], metadata, TODAY, 30) == 300.0


def test_expected_payables_excludes_beyond_horizon():
    purchases = [{"purchase_id": "P1", "total": 300.0}]
    metadata = [{"purchase_id": "P1", "due_date": (TODAY + timedelta(days=60)).isoformat()}]
    assert cf.expected_payables(purchases, [], metadata, TODAY, 30) == 0.0


# ---------------------------------------------------------------------------
# expected_recurring_expenses
# ---------------------------------------------------------------------------

def test_expected_recurring_expenses_scales_with_horizon():
    recurring = [{"amount": 100.0}]
    assert cf.expected_recurring_expenses(recurring, 30) == 100.0
    assert cf.expected_recurring_expenses(recurring, 60) == 200.0
    assert cf.expected_recurring_expenses(recurring, 90) == 300.0


def test_expected_recurring_expenses_sums_multiple_items():
    recurring = [{"amount": 100.0}, {"amount": 50.0}]
    assert cf.expected_recurring_expenses(recurring, 30) == 150.0


# ---------------------------------------------------------------------------
# expected_payroll_cost
# ---------------------------------------------------------------------------

def test_expected_payroll_cost_accounts_for_payment_frequency():
    employees = [{"status": "active", "base_salary": 400.0, "payment_frequency": "Quincenal"}]
    # Quincenal = 2 pagos por mes; 30 dias = 1 mes -> 2 * 400 = 800
    assert cf.expected_payroll_cost(employees, 30) == 800.0


def test_expected_payroll_cost_monthly_frequency():
    employees = [{"status": "active", "base_salary": 400.0, "payment_frequency": "Mensual"}]
    assert cf.expected_payroll_cost(employees, 30) == 400.0


def test_expected_payroll_cost_excludes_inactive_employees():
    employees = [{"status": "inactive", "base_salary": 999.0, "payment_frequency": "Mensual"}]
    assert cf.expected_payroll_cost(employees, 30) == 0.0


def test_expected_payroll_cost_sums_multiple_employees():
    employees = [
        {"status": "active", "base_salary": 400.0, "payment_frequency": "Mensual"},
        {"status": "active", "base_salary": 300.0, "payment_frequency": "Mensual"},
    ]
    assert cf.expected_payroll_cost(employees, 30) == 700.0


# ---------------------------------------------------------------------------
# build_forecast (consolidado)
# ---------------------------------------------------------------------------

def test_build_forecast_combines_all_components():
    cash_movements = [{"movement_type": "Ingreso", "amount": 5000.0}, {"movement_type": "Egreso", "amount": 2000.0}]
    sales = [{"sale_id": "S1", "total": 1000.0}]
    receivables_metadata = [{"sale_id": "S1", "due_date": (TODAY + timedelta(days=20)).isoformat()}]
    purchases = [{"purchase_id": "P1", "total": 300.0}]
    payables_metadata = [{"purchase_id": "P1", "due_date": (TODAY + timedelta(days=5)).isoformat()}]
    recurring = [{"amount": 100.0}]
    employees = [{"status": "active", "base_salary": 400.0, "payment_frequency": "Quincenal"}]

    forecast = cf.build_forecast(
        cash_movements, sales, [], receivables_metadata, purchases, [], payables_metadata, recurring, employees,
        horizon_days=30, as_of=TODAY,
    )

    assert forecast.current_cash == 3000.0
    assert forecast.expected_inflows == 1000.0
    assert forecast.expected_outflows == 300.0 + 100.0 + 800.0  # payables + recurring + payroll
    assert forecast.projected_cash == 3000.0 + 1000.0 - 1200.0


def test_projected_cash_can_be_negative_signaling_liquidity_risk():
    cash_movements = [{"movement_type": "Ingreso", "amount": 100.0}]
    purchases = [{"purchase_id": "P1", "total": 5000.0}]
    payables_metadata = [{"purchase_id": "P1", "due_date": (TODAY + timedelta(days=5)).isoformat()}]

    forecast = cf.build_forecast(cash_movements, [], [], [], purchases, [], payables_metadata, [], [], horizon_days=30, as_of=TODAY)

    assert forecast.projected_cash < 0
