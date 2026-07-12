"""Pruebas de RRHH y nómina (`src/payroll.py`)."""

from __future__ import annotations

from src import payroll


# ---------------------------------------------------------------------------
# Cálculo puro
# ---------------------------------------------------------------------------

def test_net_pay_sums_base_plus_bonuses_minus_deductions():
    assert payroll.net_pay(base_salary=400.0, bonuses_total=50.0, deductions_total=20.0) == 430.0


def test_net_pay_never_goes_negative():
    """Una deducción grande no debe generar una deuda con neto negativo."""
    assert payroll.net_pay(base_salary=100.0, bonuses_total=0.0, deductions_total=500.0) == 0.0


def test_period_label_formats_start_and_end():
    period = {"period_start": "2026-07-01", "period_end": "2026-07-31"}
    assert payroll.period_label(period) == "2026-07-01 → 2026-07-31"


def test_active_employees_filters_by_status():
    employees = [{"employee_id": "E1", "status": "active"}, {"employee_id": "E2", "status": "inactive"}]
    active = payroll.active_employees(employees)
    assert len(active) == 1
    assert active[0]["employee_id"] == "E1"


def test_total_payroll_cost_sums_net_of_all_entries():
    entries = [
        {"base_salary": 400.0, "bonuses_total": 50.0, "deductions_total": 20.0},  # 430
        {"base_salary": 300.0, "bonuses_total": 0.0, "deductions_total": 10.0},   # 290
    ]
    assert payroll.total_payroll_cost(entries) == 720.0


def test_total_payroll_cost_with_no_entries_is_zero():
    assert payroll.total_payroll_cost([]) == 0.0


def test_entries_pending_payment_excludes_paid():
    entries = [
        {"entry_id": "N1", "payment_status": "paid"},
        {"entry_id": "N2", "payment_status": "pending"},
    ]
    pending = payroll.entries_pending_payment(entries)
    assert len(pending) == 1
    assert pending[0]["entry_id"] == "N2"


# ---------------------------------------------------------------------------
# Flujo completo con base de datos
# ---------------------------------------------------------------------------

def test_create_and_list_employee(isolated_database):
    payroll.create_employee("Ana Pérez", "V-12345678", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")

    employees = payroll.list_employees()
    assert len(employees) == 1
    assert employees[0]["full_name"] == "Ana Pérez"
    assert employees[0]["status"] == "active"


def test_set_employee_status_deactivates(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    payroll.set_employee_status(employee_id, "inactive", "2026-07-01")

    employees = payroll.list_employees()
    assert employees[0]["status"] == "inactive"
    assert employees[0]["termination_date"] == "2026-07-01"


def test_create_period_starts_as_draft(isolated_database):
    period_id = payroll.create_period("2026-07-01", "2026-07-31")
    periods = payroll.list_periods()
    assert periods[0]["period_id"] == period_id
    assert periods[0]["status"] == "draft"


def test_close_period_sets_closed_status(isolated_database):
    period_id = payroll.create_period("2026-07-01", "2026-07-31")
    payroll.close_period(period_id)
    periods = payroll.list_periods()
    assert periods[0]["status"] == "closed"
    assert periods[0]["closed_at_utc"] is not None


def test_create_entry_and_read_back(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    period_id = payroll.create_period("2026-07-01", "2026-07-31")

    payroll.create_entry(period_id, employee_id, 400.0, 50.0, "Bono", 20.0, "Adelanto", "USD")

    entries = payroll.entries_for_period(period_id)
    assert len(entries) == 1
    assert entries[0]["full_name"] == "Ana Pérez"
    assert entries[0]["payment_status"] == "pending"


def test_create_entry_twice_for_same_employee_updates_instead_of_duplicating(isolated_database):
    """UNIQUE(period_id, employee_id) + ON CONFLICT: corregir un recibo no debe duplicarlo."""
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    period_id = payroll.create_period("2026-07-01", "2026-07-31")

    payroll.create_entry(period_id, employee_id, 400.0, 0.0, "", 0.0, "", "USD")
    payroll.create_entry(period_id, employee_id, 450.0, 20.0, "Corrección", 0.0, "", "USD")

    entries = payroll.entries_for_period(period_id)
    assert len(entries) == 1
    assert entries[0]["base_salary"] == 450.0
    assert entries[0]["bonuses_total"] == 20.0


def test_mark_entry_paid_updates_status(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    period_id = payroll.create_period("2026-07-01", "2026-07-31")
    payroll.create_entry(period_id, employee_id, 400.0, 0.0, "", 0.0, "", "USD")

    entry = payroll.entries_for_period(period_id)[0]
    payroll.mark_entry_paid(entry["entry_id"])

    entries = payroll.entries_for_period(period_id)
    assert entries[0]["payment_status"] == "paid"
    assert entries[0]["paid_at_utc"] is not None


def test_entries_for_period_only_includes_that_period(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    period_1 = payroll.create_period("2026-06-01", "2026-06-30")
    period_2 = payroll.create_period("2026-07-01", "2026-07-31")
    payroll.create_entry(period_1, employee_id, 400.0, 0.0, "", 0.0, "", "USD")

    assert len(payroll.entries_for_period(period_1)) == 1
    assert len(payroll.entries_for_period(period_2)) == 0
