from datetime import date

import pytest

from src.hr_labor_domain import (
    AttendanceEntry,
    PayrollInput,
    calculate_payroll_receipt,
    calculate_social_benefits,
    vacation_days,
)


def test_vacation_days_follow_seniority_rule():
    assert vacation_days(0) == 0
    assert vacation_days(1) == 15
    assert vacation_days(2) == 16
    assert vacation_days(10) == 24
    assert vacation_days(20) == 30


def test_social_benefits_accumulate_quarterly_guarantee_and_seniority():
    result = calculate_social_benefits(
        hire_date=date(2024, 1, 1),
        as_of=date(2026, 1, 1),
        monthly_salary=900.0,
    )
    assert result.completed_years == 2
    assert result.daily_salary == pytest.approx(30.0)
    assert result.guarantee_days == pytest.approx(135.0)
    assert result.additional_seniority_days == pytest.approx(2.0)
    assert result.guarantee_amount == pytest.approx(4110.0)
    assert result.protected_amount == pytest.approx(max(result.guarantee_amount, result.termination_reference_amount))


def test_short_service_uses_five_days_per_month_or_fraction():
    result = calculate_social_benefits(
        hire_date=date(2026, 1, 1),
        as_of=date(2026, 2, 14),
        monthly_salary=600.0,
    )
    assert result.guarantee_days == pytest.approx(10.0)
    assert result.guarantee_amount == pytest.approx(200.0)


def test_attendance_reduces_pay_and_paid_leave_preserves_it():
    entries = (
        AttendanceEntry("E1", date(2026, 7, 1), 8, 8),
        AttendanceEntry("E1", date(2026, 7, 2), 8, 4, paid_leave_hours=4),
        AttendanceEntry("E1", date(2026, 7, 3), 8, 4, unpaid_leave_hours=4),
    )
    receipt = calculate_payroll_receipt(PayrollInput(
        employee_id="E1",
        employee_name="Ana",
        monthly_salary=240.0,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 3),
        expected_hours=24.0,
        attendance=entries,
    ))
    assert receipt.payable_hours == pytest.approx(20.0)
    assert receipt.absent_hours == pytest.approx(4.0)
    assert receipt.base_salary_earned == pytest.approx(200.0)
    assert receipt.net_pay == pytest.approx(200.0)


def test_receipt_balances_with_payroll_components():
    receipt = calculate_payroll_receipt(PayrollInput(
        employee_id="E1",
        employee_name="Ana",
        monthly_salary=160.0,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        expected_hours=16.0,
        attendance=(
            AttendanceEntry("E1", date(2026, 7, 1), 8, 8, overtime_hours=2),
            AttendanceEntry("E1", date(2026, 7, 2), 8, 8),
        ),
        commissions=20.0,
        bonuses=10.0,
        other_earnings=5.0,
        deductions=15.0,
    ))
    assert receipt.base_salary_earned == pytest.approx(160.0)
    assert receipt.overtime_pay == pytest.approx(30.0)
    assert receipt.gross_pay == pytest.approx(225.0)
    assert receipt.net_pay == pytest.approx(210.0)
    exported = receipt.as_export_row()
    assert exported["gross_pay"] - exported["deductions"] == exported["net_pay"]


def test_invalid_expected_hours_is_rejected():
    with pytest.raises(ValueError):
        calculate_payroll_receipt(PayrollInput(
            employee_id="E1",
            employee_name="Ana",
            monthly_salary=100.0,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            expected_hours=0,
        ))
