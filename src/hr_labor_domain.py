"""Dominio puro para asistencia, vacaciones, nómina y prestaciones sociales.

Las reglas legales son parametrizables y deben validarse con asesoría laboral antes
de usarse para liquidaciones definitivas. La implementación base sigue LOTTT arts.
142 y 190: garantía trimestral de 15 días, días adicionales por antigüedad y
vacaciones de 15 días hábiles más un día por año sucesivo, hasta 15 adicionales.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from math import ceil
from typing import Iterable


@dataclass(frozen=True)
class AttendanceEntry:
    employee_id: str
    work_date: date
    scheduled_hours: float
    worked_hours: float
    paid_leave_hours: float = 0.0
    unpaid_leave_hours: float = 0.0
    overtime_hours: float = 0.0
    status: str = "Registrado"

    def payable_regular_hours(self) -> float:
        return max(min(self.worked_hours + self.paid_leave_hours, self.scheduled_hours), 0.0)


@dataclass(frozen=True)
class PayrollInput:
    employee_id: str
    employee_name: str
    monthly_salary: float
    period_start: date
    period_end: date
    expected_hours: float
    attendance: tuple[AttendanceEntry, ...] = field(default_factory=tuple)
    commissions: float = 0.0
    bonuses: float = 0.0
    other_earnings: float = 0.0
    deductions: float = 0.0
    overtime_multiplier: float = 1.5
    currency: str = "USD"


@dataclass(frozen=True)
class PayrollReceipt:
    employee_id: str
    employee_name: str
    period_start: date
    period_end: date
    currency: str
    base_salary_earned: float
    overtime_pay: float
    commissions: float
    bonuses: float
    other_earnings: float
    gross_pay: float
    deductions: float
    net_pay: float
    expected_hours: float
    payable_hours: float
    absent_hours: float

    def as_export_row(self) -> dict[str, object]:
        return {
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "currency": self.currency,
            "base_salary_earned": round(self.base_salary_earned, 2),
            "overtime_pay": round(self.overtime_pay, 2),
            "commissions": round(self.commissions, 2),
            "bonuses": round(self.bonuses, 2),
            "other_earnings": round(self.other_earnings, 2),
            "gross_pay": round(self.gross_pay, 2),
            "deductions": round(self.deductions, 2),
            "net_pay": round(self.net_pay, 2),
            "expected_hours": round(self.expected_hours, 2),
            "payable_hours": round(self.payable_hours, 2),
            "absent_hours": round(self.absent_hours, 2),
        }


@dataclass(frozen=True)
class SocialBenefitsResult:
    service_days: int
    completed_years: int
    guarantee_days: float
    additional_seniority_days: float
    termination_reference_days: float
    daily_salary: float
    guarantee_amount: float
    termination_reference_amount: float
    protected_amount: float


def _validate_non_negative(name: str, value: float) -> float:
    number = float(value)
    if number < 0:
        raise ValueError(f"{name} no puede ser negativo.")
    return number


def vacation_days(completed_years: int) -> int:
    """Días hábiles de vacaciones: 15 al primer año + 1 por año sucesivo, máx. 30."""
    years = int(completed_years)
    if years < 1:
        return 0
    return 15 + min(years - 1, 15)


def service_days(hire_date: date, as_of: date) -> int:
    if as_of < hire_date:
        raise ValueError("La fecha de corte no puede ser anterior al ingreso.")
    return (as_of - hire_date).days + 1


def completed_service_years(hire_date: date, as_of: date) -> int:
    years = as_of.year - hire_date.year
    if (as_of.month, as_of.day) < (hire_date.month, hire_date.day):
        years -= 1
    return max(years, 0)


def calculate_social_benefits(
    *,
    hire_date: date,
    as_of: date,
    monthly_salary: float,
) -> SocialBenefitsResult:
    """Calcula acumulado referencial de prestaciones conforme a reglas base LOTTT.

    - Garantía: 15 días por trimestre iniciado.
    - Adicional: 2 días por año después del primero, acumulativos hasta 30 días.
    - Referencia al terminar: 30 días por año o fracción superior a seis meses.
    - Si el servicio es menor de tres meses: 5 días por mes o fracción.
    """
    salary = _validate_non_negative("monthly_salary", monthly_salary)
    days = service_days(hire_date, as_of)
    years = completed_service_years(hire_date, as_of)
    daily = salary / 30.0

    service_months = max(ceil(days / 30.0), 1)
    if service_months < 3:
        guarantee_days = 5.0 * service_months
    else:
        started_quarters = ceil(service_months / 3.0)
        guarantee_days = 15.0 * started_quarters

    additional_days = min(max(years - 1, 0) * 2.0, 30.0)
    guarantee_total_days = guarantee_days + additional_days

    anniversary = date(as_of.year, hire_date.month, min(hire_date.day, 28))
    remainder_days = max((as_of - anniversary).days, 0) if years > 0 else days
    termination_years = years + (1 if remainder_days > 183 else 0)
    if years == 0 and days > 183:
        termination_years = 1
    termination_days = 30.0 * termination_years

    guarantee_amount = guarantee_total_days * daily
    termination_amount = termination_days * daily
    return SocialBenefitsResult(
        service_days=days,
        completed_years=years,
        guarantee_days=guarantee_days,
        additional_seniority_days=additional_days,
        termination_reference_days=termination_days,
        daily_salary=daily,
        guarantee_amount=guarantee_amount,
        termination_reference_amount=termination_amount,
        protected_amount=max(guarantee_amount, termination_amount),
    )


def calculate_payroll_receipt(data: PayrollInput) -> PayrollReceipt:
    salary = _validate_non_negative("monthly_salary", data.monthly_salary)
    expected = _validate_non_negative("expected_hours", data.expected_hours)
    if expected <= 0:
        raise ValueError("expected_hours debe ser mayor que cero.")

    entries = [entry for entry in data.attendance if entry.employee_id == data.employee_id]
    payable_hours = sum(entry.payable_regular_hours() for entry in entries)
    overtime_hours = sum(max(entry.overtime_hours, 0.0) for entry in entries)
    payable_hours = min(payable_hours, expected)
    absent_hours = max(expected - payable_hours, 0.0)

    hourly_rate = salary / expected
    base_earned = hourly_rate * payable_hours
    overtime_pay = hourly_rate * overtime_hours * float(data.overtime_multiplier)
    gross = (
        base_earned
        + overtime_pay
        + _validate_non_negative("commissions", data.commissions)
        + _validate_non_negative("bonuses", data.bonuses)
        + _validate_non_negative("other_earnings", data.other_earnings)
    )
    deductions = _validate_non_negative("deductions", data.deductions)
    net = gross - deductions

    return PayrollReceipt(
        employee_id=data.employee_id,
        employee_name=data.employee_name,
        period_start=data.period_start,
        period_end=data.period_end,
        currency=data.currency,
        base_salary_earned=base_earned,
        overtime_pay=overtime_pay,
        commissions=float(data.commissions),
        bonuses=float(data.bonuses),
        other_earnings=float(data.other_earnings),
        gross_pay=gross,
        deductions=deductions,
        net_pay=net,
        expected_hours=expected,
        payable_hours=payable_hours,
        absent_hours=absent_hours,
    )


def attendance_summary(entries: Iterable[AttendanceEntry]) -> dict[str, float]:
    rows = tuple(entries)
    scheduled = sum(max(row.scheduled_hours, 0.0) for row in rows)
    worked = sum(max(row.worked_hours, 0.0) for row in rows)
    paid_leave = sum(max(row.paid_leave_hours, 0.0) for row in rows)
    unpaid_leave = sum(max(row.unpaid_leave_hours, 0.0) for row in rows)
    overtime = sum(max(row.overtime_hours, 0.0) for row in rows)
    payable = sum(row.payable_regular_hours() for row in rows)
    return {
        "scheduled_hours": scheduled,
        "worked_hours": worked,
        "paid_leave_hours": paid_leave,
        "unpaid_leave_hours": unpaid_leave,
        "overtime_hours": overtime,
        "payable_regular_hours": payable,
        "absence_hours": max(scheduled - payable, 0.0),
    }
