"""Extensión visual para expediente, asistencia, vacaciones y prestaciones."""

from __future__ import annotations

import csv
import io
from datetime import date

import streamlit as st

from src import session_backup
from src.components import render_page_header
from src.hr_labor_domain import (
    AttendanceEntry,
    PayrollInput,
    attendance_summary,
    calculate_payroll_receipt,
    calculate_social_benefits,
    vacation_days,
)
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


SECTIONS = (
    ("employees_registry", "Expedientes de empleados"),
    ("employee_documents", "Documentos de empleados"),
    ("attendance_records", "Asistencia y horas"),
    ("employee_leave_requests", "Vacaciones y permisos"),
    ("social_benefits_snapshots", "Acumulados de prestaciones sociales"),
    ("payroll_receipts", "Recibos de pago"),
)


def activate_hr_labor_support() -> None:
    for section, label in SECTIONS:
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = (
        "general_settings",
        *session_backup.LIST_SECTIONS,
        *session_backup.DICT_SECTIONS,
    )


activate_hr_labor_support()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_date(value, fallback: date | None = None) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return fallback


def _employee_options(employees: list[dict]) -> dict[str, str]:
    return {
        f"{row.get('name') or row.get('employee_name') or 'Empleado'} · {row.get('employee_id', '')}": str(row.get("employee_id", ""))
        for row in employees
        if row.get("employee_id")
    }


def _export_receipt(row: dict) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Concepto", "Monto"])
    for key in ("base_salary_earned", "overtime_pay", "commissions", "bonuses", "other_earnings", "gross_pay", "deductions", "net_pay"):
        writer.writerow([key, row.get(key, 0)])
    writer.writerow([])
    writer.writerow(["Empleado", row.get("employee_name", "")])
    writer.writerow(["Período", f"{row.get('period_start', '')} al {row.get('period_end', '')}"])
    writer.writerow(["Moneda", row.get("currency", "")])
    return buffer.getvalue().encode("utf-8-sig")


def render_hr_labor_management() -> None:
    render_page_header(
        "RRHH y nómina",
        "Controla expedientes, asistencia, permisos, vacaciones, prestaciones y recibos de pago.",
    )
    employees = _rows("employees_registry")
    attendance = _rows("attendance_records")
    leaves = _rows("employee_leave_requests")
    documents = _rows("employee_documents")
    benefits = _rows("social_benefits_snapshots")
    receipts = _rows("payroll_receipts")

    tabs = st.tabs(("Expediente", "Asistencia", "Vacaciones y permisos", "Prestaciones", "Recibos"))

    with tabs[0]:
        with st.form("employee_record_form", clear_on_submit=True):
            cols = st.columns(3)
            employee_id = cols[0].text_input("Código del empleado")
            name = cols[1].text_input("Nombre completo")
            identity = cols[2].text_input("Cédula")
            cols = st.columns(3)
            hire_date = cols[0].date_input("Fecha de ingreso", value=date.today())
            position = cols[1].text_input("Cargo")
            monthly_salary = cols[2].number_input("Salario mensual", min_value=0.0, step=1.0)
            contract_type = st.selectbox("Tipo de contrato", ("Tiempo indeterminado", "Tiempo determinado", "Por obra", "Otro"))
            contact = st.text_input("Teléfono o correo")
            submitted = st.form_submit_button("Guardar expediente", type="primary", use_container_width=True)
        if submitted and employee_id.strip() and name.strip():
            employees.append({
                "employee_id": employee_id.strip(),
                "name": name.strip(),
                "identity": identity.strip(),
                "hire_date": hire_date.isoformat(),
                "position": position.strip(),
                "monthly_salary": float(monthly_salary),
                "contract_type": contract_type,
                "contact": contact.strip(),
                "created_at_utc": _now(),
            })
            _save("employees_registry", employees)
            st.rerun()
        if employees:
            st.dataframe(employees, use_container_width=True, hide_index=True)

    options = _employee_options(employees)
    if not options:
        for tab in tabs[1:]:
            with tab:
                st.info("Primero registra al menos un empleado en el expediente.")
        return

    with tabs[1]:
        selected = st.selectbox("Empleado", tuple(options), key="attendance_employee")
        employee_id = options[selected]
        with st.form("attendance_form", clear_on_submit=True):
            cols = st.columns(4)
            work_date = cols[0].date_input("Fecha", value=date.today())
            scheduled = cols[1].number_input("Horas programadas", min_value=0.0, value=8.0, step=0.5)
            worked = cols[2].number_input("Horas trabajadas", min_value=0.0, value=8.0, step=0.5)
            overtime = cols[3].number_input("Horas extra", min_value=0.0, step=0.5)
            cols = st.columns(2)
            paid_leave = cols[0].number_input("Permiso remunerado (h)", min_value=0.0, step=0.5)
            unpaid_leave = cols[1].number_input("Permiso no remunerado (h)", min_value=0.0, step=0.5)
            submitted = st.form_submit_button("Registrar asistencia", type="primary", use_container_width=True)
        if submitted:
            attendance.append({
                "employee_id": employee_id,
                "work_date": work_date.isoformat(),
                "scheduled_hours": float(scheduled),
                "worked_hours": float(worked),
                "paid_leave_hours": float(paid_leave),
                "unpaid_leave_hours": float(unpaid_leave),
                "overtime_hours": float(overtime),
                "created_at_utc": _now(),
            })
            _save("attendance_records", attendance)
            st.rerun()
        entries = [
            AttendanceEntry(
                employee_id=employee_id,
                work_date=_as_date(row.get("work_date"), date.today()) or date.today(),
                scheduled_hours=_num(row.get("scheduled_hours")),
                worked_hours=_num(row.get("worked_hours")),
                paid_leave_hours=_num(row.get("paid_leave_hours")),
                unpaid_leave_hours=_num(row.get("unpaid_leave_hours")),
                overtime_hours=_num(row.get("overtime_hours")),
            )
            for row in attendance if str(row.get("employee_id")) == employee_id
        ]
        if entries:
            summary = attendance_summary(entries)
            cols = st.columns(4)
            cols[0].metric("Programadas", f"{summary['scheduled_hours']:.1f} h")
            cols[1].metric("Trabajadas", f"{summary['worked_hours']:.1f} h")
            cols[2].metric("Ausencia", f"{summary['absence_hours']:.1f} h")
            cols[3].metric("Extras", f"{summary['overtime_hours']:.1f} h")

    with tabs[2]:
        selected = st.selectbox("Empleado", tuple(options), key="leave_employee")
        employee_id = options[selected]
        employee = next(row for row in employees if str(row.get("employee_id")) == employee_id)
        years = 0
        hire = _as_date(employee.get("hire_date"))
        if hire:
            years = max(date.today().year - hire.year - ((date.today().month, date.today().day) < (hire.month, hire.day)), 0)
        st.metric("Vacaciones legales disponibles por antigüedad", f"{vacation_days(years)} días hábiles")
        with st.form("leave_form", clear_on_submit=True):
            leave_type = st.selectbox("Tipo", ("Vacaciones", "Permiso remunerado", "Permiso no remunerado", "Reposo", "Otro"))
            cols = st.columns(2)
            start = cols[0].date_input("Desde", value=date.today())
            end = cols[1].date_input("Hasta", value=date.today())
            reason = st.text_area("Motivo")
            submitted = st.form_submit_button("Registrar solicitud", type="primary", use_container_width=True)
        if submitted:
            leaves.append({"employee_id": employee_id, "leave_type": leave_type, "start_date": start.isoformat(), "end_date": end.isoformat(), "reason": reason.strip(), "status": "Pendiente", "created_at_utc": _now()})
            _save("employee_leave_requests", leaves)
            st.rerun()

    with tabs[3]:
        selected = st.selectbox("Empleado", tuple(options), key="benefits_employee")
        employee_id = options[selected]
        employee = next(row for row in employees if str(row.get("employee_id")) == employee_id)
        hire = _as_date(employee.get("hire_date"))
        if not hire:
            st.warning("El expediente no tiene fecha de ingreso válida.")
        else:
            result = calculate_social_benefits(hire_date=hire, as_of=date.today(), monthly_salary=_num(employee.get("monthly_salary")))
            cols = st.columns(4)
            cols[0].metric("Días de garantía", f"{result.guarantee_days + result.additional_seniority_days:.1f}")
            cols[1].metric("Garantía acumulada", f"{result.guarantee_amount:,.2f}")
            cols[2].metric("Referencia al terminar", f"{result.termination_reference_amount:,.2f}")
            cols[3].metric("Monto protegido", f"{result.protected_amount:,.2f}")
            if st.button("Guardar corte de prestaciones", type="primary", use_container_width=True):
                benefits.append({"employee_id": employee_id, "as_of": date.today().isoformat(), **result.__dict__, "created_at_utc": _now()})
                _save("social_benefits_snapshots", benefits)
                st.rerun()
            st.caption("Cálculo referencial basado en reglas generales de la LOTTT. Requiere revisión profesional para liquidaciones definitivas, intereses, salario integral y casos especiales.")

    with tabs[4]:
        selected = st.selectbox("Empleado", tuple(options), key="receipt_employee")
        employee_id = options[selected]
        employee = next(row for row in employees if str(row.get("employee_id")) == employee_id)
        with st.form("receipt_form"):
            cols = st.columns(3)
            start = cols[0].date_input("Inicio del período", value=date.today().replace(day=1))
            end = cols[1].date_input("Fin del período", value=date.today())
            expected_hours = cols[2].number_input("Horas esperadas", min_value=0.5, value=160.0, step=1.0)
            cols = st.columns(4)
            commissions = cols[0].number_input("Comisiones", min_value=0.0)
            bonuses = cols[1].number_input("Bonos", min_value=0.0)
            other = cols[2].number_input("Otros ingresos", min_value=0.0)
            deductions = cols[3].number_input("Deducciones", min_value=0.0)
            submitted = st.form_submit_button("Generar recibo", type="primary", use_container_width=True)
        if submitted:
            period_entries = []
            for row in attendance:
                row_date = _as_date(row.get("work_date"))
                if str(row.get("employee_id")) == employee_id and row_date and start <= row_date <= end:
                    period_entries.append(AttendanceEntry(employee_id=employee_id, work_date=row_date, scheduled_hours=_num(row.get("scheduled_hours")), worked_hours=_num(row.get("worked_hours")), paid_leave_hours=_num(row.get("paid_leave_hours")), unpaid_leave_hours=_num(row.get("unpaid_leave_hours")), overtime_hours=_num(row.get("overtime_hours"))))
            receipt = calculate_payroll_receipt(PayrollInput(employee_id=employee_id, employee_name=str(employee.get("name", "Empleado")), monthly_salary=_num(employee.get("monthly_salary")), period_start=start, period_end=end, expected_hours=float(expected_hours), attendance=tuple(period_entries), commissions=float(commissions), bonuses=float(bonuses), other_earnings=float(other), deductions=float(deductions)))
            row = {"receipt_id": f"PAY-{len(receipts)+1:06d}", **receipt.as_export_row(), "created_at_utc": _now()}
            receipts.append(row)
            _save("payroll_receipts", receipts)
            st.success("Recibo generado y guardado.")
        employee_receipts = [row for row in receipts if str(row.get("employee_id")) == employee_id]
        if employee_receipts:
            latest = employee_receipts[-1]
            cols = st.columns(3)
            cols[0].metric("Devengado", f"{_num(latest.get('gross_pay')):,.2f}")
            cols[1].metric("Deducciones", f"{_num(latest.get('deductions')):,.2f}")
            cols[2].metric("Neto", f"{_num(latest.get('net_pay')):,.2f}")
            st.download_button("Exportar último recibo CSV", data=_export_receipt(latest), file_name=f"recibo_{employee_id}_{latest.get('period_end','')}.csv", mime="text/csv", use_container_width=True)
