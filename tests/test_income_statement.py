"""Pruebas del Estado de Resultados (`src/income_statement.py`)."""

from __future__ import annotations

from src import income_statement as inc


# ---------------------------------------------------------------------------
# Componentes individuales
# ---------------------------------------------------------------------------

def test_revenue_for_month_sums_matching_sales():
    sales = [
        {"total": 1000.0, "order_status": "Entregado", "created_at_utc": "2026-07-05T10:00:00"},
        {"total": 300.0, "order_status": "Entregado", "created_at_utc": "2026-06-01T10:00:00"},
    ]
    assert inc.revenue_for_month(sales, "2026-07") == 1000.0


def test_revenue_for_month_excludes_cancelled_sales():
    sales = [
        {"total": 1000.0, "order_status": "Entregado", "created_at_utc": "2026-07-05T10:00:00"},
        {"total": 500.0, "order_status": "Cancelado", "created_at_utc": "2026-07-06T10:00:00"},
    ]
    assert inc.revenue_for_month(sales, "2026-07") == 1000.0


def test_cogs_for_month_sums_estimated_cost():
    sales = [{"total": 1000.0, "estimated_cost": 400.0, "order_status": "Entregado", "created_at_utc": "2026-07-05T10:00:00"}]
    assert inc.cogs_for_month(sales, "2026-07") == 400.0


def test_cogs_for_month_defaults_to_zero_when_missing():
    sales = [{"total": 1000.0, "order_status": "Entregado", "created_at_utc": "2026-07-05T10:00:00"}]
    assert inc.cogs_for_month(sales, "2026-07") == 0.0


def test_operating_expenses_for_month_filters_by_expense_date():
    expenses = [
        {"amount": 150.0, "expense_date": "2026-07-10"},
        {"amount": 50.0, "expense_date": "2026-06-10"},
    ]
    assert inc.operating_expenses_for_month(expenses, "2026-07") == 150.0


def test_operating_expenses_by_category_groups_correctly():
    expenses = [
        {"amount": 100.0, "category": "Internet", "expense_date": "2026-07-01"},
        {"amount": 50.0, "category": "Internet", "expense_date": "2026-07-15"},
        {"amount": 30.0, "category": "Software", "expense_date": "2026-07-20"},
    ]
    result = inc.operating_expenses_by_category(expenses, "2026-07")
    assert result == {"Internet": 150.0, "Software": 30.0}


def test_operating_expenses_by_category_defaults_missing_category_to_otro():
    expenses = [{"amount": 20.0, "expense_date": "2026-07-01"}]
    result = inc.operating_expenses_by_category(expenses, "2026-07")
    assert result == {"Otro": 20.0}


def test_payroll_cost_for_month_sums_net_pay_for_matching_period():
    entries = [
        {"base_salary": 400.0, "bonuses_total": 50.0, "deductions_total": 20.0, "period_month": "2026-07"},
        {"base_salary": 300.0, "bonuses_total": 0.0, "deductions_total": 0.0, "period_month": "2026-06"},
    ]
    assert inc.payroll_cost_for_month(entries, "2026-07") == 430.0


# ---------------------------------------------------------------------------
# Mantenimiento de activos: gasto real que antes no llegaba al P&L
# ---------------------------------------------------------------------------

def test_asset_maintenance_for_month_uses_inline_log_event_date():
    entries = [{"asset_id": "AST-1", "cost": 40.0, "event_date": "2026-07-03"}]
    assert inc.asset_maintenance_for_month(entries, "2026-07") == 40.0


def test_asset_maintenance_for_month_uses_governance_log_maintenance_date():
    entries = [{"asset_id": "AST-1", "cost": 25.0, "maintenance_date": "2026-07-10"}]
    assert inc.asset_maintenance_for_month(entries, "2026-07") == 25.0


def test_asset_maintenance_for_month_combines_both_logs_and_filters_by_month():
    entries = [
        {"asset_id": "AST-1", "cost": 40.0, "event_date": "2026-07-03"},
        {"asset_id": "AST-2", "cost": 25.0, "maintenance_date": "2026-07-10"},
        {"asset_id": "AST-3", "cost": 99.0, "event_date": "2026-06-30"},
    ]
    assert inc.asset_maintenance_for_month(entries, "2026-07") == 65.0


def test_asset_maintenance_for_month_falls_back_to_created_at_when_no_explicit_date():
    entries = [{"asset_id": "AST-1", "cost": 15.0, "created_at_utc": "2026-07-20T12:00:00+00:00"}]
    assert inc.asset_maintenance_for_month(entries, "2026-07") == 15.0


def test_asset_maintenance_for_month_reads_preventive_performed_date():
    """El Mantenimiento preventivo (por máquina, en base de datos) usa
    `performed_date`; también debe contar en el gasto de mantenimiento del P&L."""
    entries = [{"machine_id": "MCH-1", "cost": 25.0, "performed_date": "2026-07-14"}]
    assert inc.asset_maintenance_for_month(entries, "2026-07") == 25.0


def test_asset_maintenance_for_month_combines_all_three_sources():
    entries = [
        {"asset_id": "AST-1", "cost": 40.0, "event_date": "2026-07-03"},        # bitácora en línea
        {"asset_id": "AST-2", "cost": 25.0, "maintenance_date": "2026-07-10"},  # bitácora administrativa
        {"machine_id": "MCH-1", "cost": 30.0, "performed_date": "2026-07-14"},  # preventivo por máquina
    ]
    assert inc.asset_maintenance_for_month(entries, "2026-07") == 95.0


# ---------------------------------------------------------------------------
# Estado de resultados consolidado
# ---------------------------------------------------------------------------

def test_build_income_statement_combines_all_components():
    sales = [{"total": 1000.0, "estimated_cost": 400.0, "order_status": "Entregado", "created_at_utc": "2026-07-05T10:00:00"}]
    expenses = [{"amount": 150.0, "category": "Internet", "expense_date": "2026-07-10"}]
    payroll_entries = [{"base_salary": 400.0, "bonuses_total": 0.0, "deductions_total": 0.0, "period_month": "2026-07"}]

    statement = inc.build_income_statement(sales, expenses, payroll_entries, "2026-07")

    assert statement.revenue == 1000.0
    assert statement.cogs == 400.0
    assert statement.gross_profit == 600.0
    assert statement.operating_expenses == 150.0
    assert statement.payroll_cost == 400.0
    assert statement.asset_maintenance == 0.0
    assert statement.net_profit == 50.0


def test_build_income_statement_subtracts_asset_maintenance_from_net_profit():
    sales = [{"total": 1000.0, "estimated_cost": 400.0, "order_status": "Entregado", "created_at_utc": "2026-07-05T10:00:00"}]
    expenses = [{"amount": 150.0, "category": "Internet", "expense_date": "2026-07-10"}]
    payroll_entries = [{"base_salary": 400.0, "bonuses_total": 0.0, "deductions_total": 0.0, "period_month": "2026-07"}]
    maintenance = [{"asset_id": "AST-1", "cost": 30.0, "event_date": "2026-07-12"}]

    statement = inc.build_income_statement(sales, expenses, payroll_entries, "2026-07", maintenance)

    assert statement.asset_maintenance == 30.0
    # utilidad neta anterior (50) menos el mantenimiento (30) => 20
    assert statement.net_profit == 20.0


def test_build_income_statement_maintenance_defaults_to_zero_when_omitted():
    """Compatibilidad: las llamadas viejas sin mantenimiento no deben cambiar."""
    sales = [{"total": 500.0, "estimated_cost": 100.0, "order_status": "Entregado", "created_at_utc": "2026-07-05T10:00:00"}]
    statement = inc.build_income_statement(sales, expenses=[], payroll_entries_with_month=[], month="2026-07")
    assert statement.asset_maintenance == 0.0
    assert statement.net_profit == 400.0


def test_income_statement_net_profit_can_be_negative():
    sales = [{"total": 100.0, "estimated_cost": 50.0, "order_status": "Entregado", "created_at_utc": "2026-07-05T10:00:00"}]
    expenses = [{"amount": 200.0, "category": "Otro", "expense_date": "2026-07-10"}]

    statement = inc.build_income_statement(sales, expenses, payroll_entries_with_month=[], month="2026-07")

    assert statement.gross_profit == 50.0
    assert statement.net_profit == -150.0


def test_gross_margin_percent_calculation():
    sales = [{"total": 200.0, "estimated_cost": 50.0, "order_status": "Entregado", "created_at_utc": "2026-07-05T10:00:00"}]
    statement = inc.build_income_statement(sales, expenses=[], payroll_entries_with_month=[], month="2026-07")
    assert statement.gross_margin_percent == 75.0  # (200-50)/200 * 100


def test_margin_percent_is_zero_when_no_revenue():
    statement = inc.build_income_statement(sales=[], expenses=[], payroll_entries_with_month=[], month="2026-07")
    assert statement.revenue == 0.0
    assert statement.gross_margin_percent == 0.0
    assert statement.net_margin_percent == 0.0


# ---------------------------------------------------------------------------
# Integración real con el módulo de nómina
# ---------------------------------------------------------------------------

def test_payroll_entries_with_month_joins_period_start(isolated_database):
    """_payroll_entries_with_month() debe combinar cada recibo con el mes de
    inicio de su período, usando el módulo de nómina real (no un mock)."""
    from src import payroll

    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    period_id = payroll.create_period("2026-07-01", "2026-07-31")
    payroll.create_entry(period_id, employee_id, 400.0, 50.0, "", 20.0, "", "USD")

    entries = inc._payroll_entries_with_month()

    assert len(entries) == 1
    assert entries[0]["period_month"] == "2026-07"
    assert inc.payroll_cost_for_month(entries, "2026-07") == 430.0
