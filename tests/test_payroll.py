"""Pruebas de RRHH y nómina (`src/payroll.py`)."""

from __future__ import annotations

from src import payroll
from src.session_utils import read_list


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


def test_time_off_days_counts_both_endpoints():
    """7 al 7 es 1 día, no 0: el primer y último día cuentan."""
    assert payroll.time_off_days("2026-07-07", "2026-07-07") == 1


def test_time_off_days_counts_full_range_inclusive():
    assert payroll.time_off_days("2026-07-01", "2026-07-10") == 10


def test_time_off_days_never_negative_when_end_before_start():
    assert payroll.time_off_days("2026-07-10", "2026-07-01") == 0


def test_salary_change_amount_positive_for_raise():
    assert payroll.salary_change_amount(previous_salary=400.0, new_salary=450.0) == 50.0


def test_salary_change_amount_negative_for_cut():
    assert payroll.salary_change_amount(previous_salary=400.0, new_salary=350.0) == -50.0


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


# ---------------------------------------------------------------------------
# mark_entry_paid — ahora también mueve Caja (antes el dinero desaparecía
# del rastro contable al pagar)
# ---------------------------------------------------------------------------

def test_mark_entry_paid_creates_cash_egreso_movement(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    period_id = payroll.create_period("2026-07-01", "2026-07-31")
    payroll.create_entry(period_id, employee_id, 400.0, 50.0, "Bono", 20.0, "", "USD")
    entry = payroll.entries_for_period(period_id)[0]

    payroll.mark_entry_paid(entry["entry_id"], payment_method="Transferencia", responsible="Gerencia")

    movements = read_list("cash_movements")
    assert len(movements) == 1
    assert movements[0]["movement_type"] == "Egreso"
    assert movements[0]["category"] == "Nómina"
    assert movements[0]["amount"] == 430.0  # 400 + 50 - 20
    assert movements[0]["payment_method"] == "Transferencia"
    assert "Ana Pérez" in movements[0]["reference"]


def test_mark_entry_paid_stores_payment_method_and_cash_movement_link(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    period_id = payroll.create_period("2026-07-01", "2026-07-31")
    payroll.create_entry(period_id, employee_id, 400.0, 0.0, "", 0.0, "", "USD")
    entry = payroll.entries_for_period(period_id)[0]

    payroll.mark_entry_paid(entry["entry_id"], payment_method="Zelle")

    updated = payroll.entries_for_period(period_id)[0]
    assert updated["payment_method"] == "Zelle"
    assert updated["cash_movement_id"] != ""


def test_mark_entry_paid_on_unknown_entry_does_not_crash(isolated_database):
    """Defensivo: un entry_id inexistente no debe romper el flujo ni crear
    movimientos fantasma en Caja."""
    payroll.mark_entry_paid("NO-EXISTE")
    assert read_list("cash_movements") == []


# ---------------------------------------------------------------------------
# Vacaciones y permisos
# ---------------------------------------------------------------------------

def test_create_time_off_computes_days_and_lists_with_employee_name(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")

    payroll.create_time_off(employee_id, "Vacaciones", "2026-08-01", "2026-08-10", paid=True, notes="Vacaciones anuales")

    records = payroll.list_time_off()
    assert len(records) == 1
    assert records[0]["full_name"] == "Ana Pérez"
    assert records[0]["days"] == 10.0
    assert records[0]["paid"] == 1


def test_list_time_off_filters_by_employee(isolated_database):
    employee_a = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    employee_b = payroll.create_employee("Beto Ruiz", "V-2", "Operador", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    payroll.create_time_off(employee_a, "Permiso", "2026-08-01", "2026-08-01", paid=False, notes="")
    payroll.create_time_off(employee_b, "Vacaciones", "2026-08-05", "2026-08-06", paid=True, notes="")

    only_a = payroll.list_time_off(employee_a)
    assert len(only_a) == 1
    assert only_a[0]["full_name"] == "Ana Pérez"


def test_create_time_off_unpaid_permission_flag(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    payroll.create_time_off(employee_id, "Permiso", "2026-08-01", "2026-08-01", paid=False, notes="Cita médica")

    record = payroll.list_time_off(employee_id)[0]
    assert record["paid"] == 0
    assert record["notes"] == "Cita médica"


# ---------------------------------------------------------------------------
# Historial de aumentos salariales
# ---------------------------------------------------------------------------

def test_change_salary_updates_employee_base_salary(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")

    payroll.change_salary(employee_id, 450.0, "USD", "2026-08-01", "Aumento anual")

    employee = payroll.list_employees()[0]
    assert employee["base_salary"] == 450.0


def test_change_salary_records_history_with_previous_and_new_amount(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")

    payroll.change_salary(employee_id, 450.0, "USD", "2026-08-01", "Aumento anual")

    history = payroll.salary_history_for_employee(employee_id)
    assert len(history) == 1
    assert history[0]["previous_salary"] == 400.0
    assert history[0]["new_salary"] == 450.0
    assert history[0]["reason"] == "Aumento anual"


def test_change_salary_second_change_uses_previous_as_new_base(isolated_database):
    """El segundo cambio debe partir del salario que dejó el primero, no del
    original — la historia debe encadenarse correctamente."""
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    payroll.change_salary(employee_id, 450.0, "USD", "2026-08-01", "Primer aumento")
    payroll.change_salary(employee_id, 500.0, "USD", "2026-09-01", "Segundo aumento")

    history = payroll.salary_history_for_employee(employee_id)
    assert len(history) == 2
    by_reason = {row["reason"]: row for row in history}
    assert by_reason["Segundo aumento"]["previous_salary"] == 450.0
    assert by_reason["Segundo aumento"]["new_salary"] == 500.0


def test_all_salary_history_includes_employee_name(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    payroll.change_salary(employee_id, 450.0, "USD", "2026-08-01", "Aumento")

    history = payroll.all_salary_history()
    assert history[0]["full_name"] == "Ana Pérez"


# ---------------------------------------------------------------------------
# Recibo de pago descargable
# ---------------------------------------------------------------------------

def test_build_payslip_html_includes_employee_name_and_net_amount():
    entry = {
        "entry_id": "NOM-1", "full_name": "Ana Pérez", "position": "Operadora",
        "base_salary": 400.0, "bonuses_total": 50.0, "deductions_total": 20.0,
        "currency": "USD", "period_start": "2026-07-01", "period_end": "2026-07-31",
        "payment_method": "Transferencia",
    }
    html = payroll.build_payslip_html(entry)
    text = html.decode("utf-8")
    assert "Ana P" in text  # nombre presente (evita depender de la codificación exacta de acentos)
    assert "Transferencia" in text
    assert "430" in text  # neto: 400 + 50 - 20


def test_build_payslip_html_escapes_html_in_notes():
    """Un detalle de bono con HTML no debe inyectarse crudo en el documento."""
    entry = {
        "entry_id": "NOM-1", "full_name": "Ana Pérez", "position": "Operadora",
        "base_salary": 400.0, "bonuses_total": 0.0, "deductions_total": 0.0,
        "currency": "USD", "bonuses_detail": "<script>alert(1)</script>",
    }
    html = payroll.build_payslip_html(entry)
    assert b"<script>" not in html


def test_entries_for_period_only_includes_that_period(isolated_database):
    employee_id = payroll.create_employee("Ana Pérez", "V-1", "Operadora", "Producción", "2026-01-15", 400.0, "USD", "Mensual")
    period_1 = payroll.create_period("2026-06-01", "2026-06-30")
    period_2 = payroll.create_period("2026-07-01", "2026-07-31")
    payroll.create_entry(period_1, employee_id, 400.0, 0.0, "", 0.0, "", "USD")

    assert len(payroll.entries_for_period(period_1)) == 1
    assert len(payroll.entries_for_period(period_2)) == 0
