"""RRHH y nómina para CopyMary ERP.

Bloqueante real detectado en la revisión de negocio (dueña + finanzas +
producción): el sistema no tenía ninguna forma de registrar empleados ni
pagarles. `team_commissions.py` incluso lo admite explícitamente: "las
comisiones... no sustituyen una nómina legal".

Alcance deliberado: registro de empleados, períodos de nómina, y recibos de
pago (salario + bonos + deducciones = neto). Este módulo NO calcula
prestaciones sociales, utilidades/aguinaldos, IVSS/FAOV, ni retenciones de
ley — esas reglas varían por país, cambian con el tiempo, y deben validarse
con un contador o abogado laboral antes de usarse para pagos reales. Lo que
sí resuelve: dejar de pagarle a la gente "de memoria" o fuera del sistema,
con historial y auditoría de cada pago.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database, record_audit_event
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now

PAYMENT_FREQUENCIES = ("Mensual", "Quincenal", "Semanal")
DEPARTMENTS = ("Producción", "Ventas", "Administración", "Diseño", "Otro")


# ---------------------------------------------------------------------------
# Cálculo puro (testeable sin base de datos)
# ---------------------------------------------------------------------------

def net_pay(base_salary: float, bonuses_total: float, deductions_total: float) -> float:
    """Neto a pagar. Nunca negativo (una deducción no puede generar una deuda)."""
    return max(base_salary + bonuses_total - deductions_total, 0.0)


def period_label(period: dict) -> str:
    return f"{period.get('period_start', '')} → {period.get('period_end', '')}"


def active_employees(employees: list[dict]) -> list[dict]:
    return [row for row in employees if row.get("status") == "active"]


def total_payroll_cost(entries: list[dict]) -> float:
    """Costo total de nómina (suma de netos) para un conjunto de recibos, ej. un período."""
    return sum(float(row.get("base_salary", 0.0)) + float(row.get("bonuses_total", 0.0)) - float(row.get("deductions_total", 0.0)) for row in entries)


def entries_pending_payment(entries: list[dict]) -> list[dict]:
    return [row for row in entries if row.get("payment_status") != "paid"]


# ---------------------------------------------------------------------------
# Acceso a datos
# ---------------------------------------------------------------------------

def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _fetch_one(query: str, params: tuple = ()) -> dict | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def list_employees() -> list[dict]:
    return _fetch_all("SELECT * FROM employees ORDER BY full_name")


def create_employee(full_name: str, national_id: str, position: str, department: str, hire_date: str, base_salary: float, salary_currency: str, payment_frequency: str, bank_name: str = "", bank_account: str = "", notes: str = "") -> str:
    initialize_database()
    employee_id = f"EMP-{uuid4().hex[:8].upper()}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO employees(employee_id, full_name, national_id, position, department, hire_date, status, base_salary, salary_currency, payment_frequency, bank_name, bank_account, notes, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
            """,
            (employee_id, full_name.strip(), national_id.strip(), position.strip(), department, hire_date, base_salary, salary_currency, payment_frequency, bank_name.strip(), bank_account.strip(), notes.strip(), _now()),
        )
    record_audit_event("rrhh", "employees", employee_id, "create", after={"full_name": full_name, "position": position})
    return employee_id


def set_employee_status(employee_id: str, status: str, termination_date: str = "") -> None:
    initialize_database()
    with connect() as conn:
        conn.execute(
            "UPDATE employees SET status = ?, termination_date = ? WHERE employee_id = ?",
            (status, termination_date or None, employee_id),
        )
    record_audit_event("rrhh", "employees", employee_id, "status_change", after={"status": status})


def list_periods() -> list[dict]:
    return _fetch_all("SELECT * FROM payroll_periods ORDER BY period_start DESC")


def create_period(period_start: str, period_end: str) -> str:
    initialize_database()
    period_id = f"PER-{uuid4().hex[:8].upper()}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO payroll_periods(period_id, period_start, period_end, status, created_at_utc) VALUES (?, ?, ?, 'draft', ?)",
            (period_id, period_start, period_end, _now()),
        )
    return period_id


def close_period(period_id: str) -> None:
    initialize_database()
    with connect() as conn:
        conn.execute(
            "UPDATE payroll_periods SET status = 'closed', closed_at_utc = ? WHERE period_id = ?",
            (_now(), period_id),
        )
    record_audit_event("rrhh", "payroll_periods", period_id, "close")


def entries_for_period(period_id: str) -> list[dict]:
    return _fetch_all(
        """
        SELECT pe.*, e.full_name, e.position
        FROM payroll_entries pe JOIN employees e ON e.employee_id = pe.employee_id
        WHERE pe.period_id = ?
        ORDER BY e.full_name
        """,
        (period_id,),
    )


def create_entry(period_id: str, employee_id: str, base_salary: float, bonuses_total: float, bonuses_detail: str, deductions_total: float, deductions_detail: str, currency: str) -> str:
    initialize_database()
    entry_id = f"NOM-{uuid4().hex[:8].upper()}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO payroll_entries(entry_id, period_id, employee_id, base_salary, bonuses_total, bonuses_detail, deductions_total, deductions_detail, currency, payment_status, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            ON CONFLICT(period_id, employee_id) DO UPDATE SET
                base_salary = excluded.base_salary,
                bonuses_total = excluded.bonuses_total,
                bonuses_detail = excluded.bonuses_detail,
                deductions_total = excluded.deductions_total,
                deductions_detail = excluded.deductions_detail,
                currency = excluded.currency
            """,
            (entry_id, period_id, employee_id, base_salary, bonuses_total, bonuses_detail.strip(), deductions_total, deductions_detail.strip(), currency, _now()),
        )
    return entry_id


def mark_entry_paid(entry_id: str) -> None:
    initialize_database()
    with connect() as conn:
        conn.execute(
            "UPDATE payroll_entries SET payment_status = 'paid', paid_at_utc = ? WHERE entry_id = ?",
            (_now(), entry_id),
        )
    record_audit_event("rrhh", "payroll_entries", entry_id, "pay")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def render_payroll() -> None:
    render_page_header("RRHH y nómina", "Registro de empleados y recibos de pago por período.")
    st.caption("Este módulo calcula salario + bonos − deducciones = neto, con historial y auditoría. No calcula prestaciones sociales, utilidades ni retenciones de ley — valida esas reglas con un contador antes de usarlas para pagos reales.")

    employees = list_employees()
    periods = list_periods()
    currency = get_currency()

    employees_tab, periods_tab = st.tabs(("Empleados", "Períodos de nómina"))

    with employees_tab:
        active = active_employees(employees)
        cols = st.columns(3)
        cols[0].metric("Empleados", str(len(employees)))
        cols[1].metric("Activos", str(len(active)))
        cols[2].metric("Nómina mensual estimada", format_money(sum(row.get("base_salary", 0.0) for row in active), currency))

        with st.expander("Registrar empleado", expanded=not employees):
            with st.form("employee_form", clear_on_submit=True):
                full_name = st.text_input("Nombre completo")
                national_id = st.text_input("Cédula / documento")
                position = st.text_input("Cargo")
                department = st.selectbox("Departamento", DEPARTMENTS)
                hire_date = st.date_input("Fecha de ingreso", value=date.today())
                salary_col, currency_col, frequency_col = st.columns(3)
                base_salary = salary_col.number_input("Salario base", min_value=0.0, step=10.0)
                salary_currency = currency_col.selectbox("Moneda", ("USD", "VES", "EUR"))
                payment_frequency = frequency_col.selectbox("Frecuencia de pago", PAYMENT_FREQUENCIES)
                bank_name = st.text_input("Banco (opcional)")
                bank_account = st.text_input("Cuenta (opcional)")
                submitted = st.form_submit_button("Registrar empleado", type="primary", use_container_width=True)
            if submitted:
                if not full_name.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    create_employee(full_name, national_id, position, department, hire_date.isoformat(), base_salary, salary_currency, payment_frequency, bank_name, bank_account)
                    st.success(f"Empleado '{full_name}' registrado.")
                    st.rerun()

        for row in employees:
            with st.container(border=True):
                cols = st.columns([3, 2, 2, 1])
                cols[0].markdown(f"**{row['full_name']}** · {row.get('position', '')}")
                cols[1].write(f"{row.get('department', '')}")
                cols[2].write(format_money(row.get("base_salary", 0.0), row.get("salary_currency", "USD")) + f" / {row.get('payment_frequency', '')}")
                status = row.get("status", "active")
                if cols[3].button("Desactivar" if status == "active" else "Reactivar", key=f"toggle_{row['employee_id']}"):
                    set_employee_status(row["employee_id"], "inactive" if status == "active" else "active")
                    st.rerun()

    with periods_tab:
        with st.expander("Crear período de nómina", expanded=not periods):
            with st.form("period_form", clear_on_submit=True):
                cols = st.columns(2)
                period_start = cols[0].date_input("Inicio del período", value=date.today().replace(day=1))
                period_end = cols[1].date_input("Fin del período", value=date.today())
                submitted_period = st.form_submit_button("Crear período", type="primary", use_container_width=True)
            if submitted_period:
                create_period(period_start.isoformat(), period_end.isoformat())
                st.success("Período creado.")
                st.rerun()

        if not periods:
            st.info("Crea un período para empezar a registrar recibos de pago.")
            return

        period_options = {period_label(period): period for period in periods}
        selected_label = st.selectbox("Período", tuple(period_options.keys()))
        selected_period = period_options[selected_label]
        entries = entries_for_period(selected_period["period_id"])
        is_closed = selected_period.get("status") == "closed"

        cols = st.columns(3)
        cols[0].metric("Estado", "Cerrado" if is_closed else "Borrador")
        cols[1].metric("Recibos", str(len(entries)))
        cols[2].metric("Costo total del período", format_money(total_payroll_cost(entries), currency))

        if not is_closed:
            active = active_employees(employees)
            existing_ids = {row["employee_id"] for row in entries}
            pending_employees = [row for row in active if row["employee_id"] not in existing_ids]
            if pending_employees:
                with st.expander("Agregar recibo de pago"):
                    employee_options = {f"{row['full_name']} · {row.get('position', '')}": row for row in pending_employees}
                    with st.form("entry_form", clear_on_submit=True):
                        employee_label = st.selectbox("Empleado", tuple(employee_options.keys()))
                        employee_row = employee_options[employee_label]
                        base_salary = st.number_input("Salario base del período", min_value=0.0, value=float(employee_row.get("base_salary", 0.0)), step=10.0)
                        bonus_col, deduction_col = st.columns(2)
                        bonuses_total = bonus_col.number_input("Bonos", min_value=0.0, step=5.0)
                        bonuses_detail = bonus_col.text_input("Detalle de bonos (opcional)")
                        deductions_total = deduction_col.number_input("Deducciones", min_value=0.0, step=5.0)
                        deductions_detail = deduction_col.text_input("Detalle de deducciones (opcional)")
                        st.metric("Neto a pagar", format_money(net_pay(base_salary, bonuses_total, deductions_total), employee_row.get("salary_currency", "USD")))
                        submitted_entry = st.form_submit_button("Agregar recibo", type="primary", use_container_width=True)
                    if submitted_entry:
                        create_entry(selected_period["period_id"], employee_row["employee_id"], base_salary, bonuses_total, bonuses_detail, deductions_total, deductions_detail, employee_row.get("salary_currency", "USD"))
                        st.success("Recibo agregado.")
                        st.rerun()

        for row in entries:
            with st.container(border=True):
                net = net_pay(row.get("base_salary", 0.0), row.get("bonuses_total", 0.0), row.get("deductions_total", 0.0))
                cols = st.columns([3, 2, 2, 1])
                cols[0].markdown(f"**{row['full_name']}** · {row.get('position', '')}")
                cols[1].write(f"Base {format_money(row.get('base_salary', 0.0), row.get('currency', 'USD'))}")
                cols[2].write(f"Neto {format_money(net, row.get('currency', 'USD'))}")
                if row.get("payment_status") == "paid":
                    cols[3].write("✅ Pagado")
                elif cols[3].button("Pagar", key=f"pay_{row['entry_id']}"):
                    mark_entry_paid(row["entry_id"])
                    st.rerun()

        if not is_closed and entries and not entries_pending_payment(entries):
            if st.button("Cerrar período", type="primary"):
                close_period(selected_period["period_id"])
                st.rerun()
        elif not is_closed and entries_pending_payment(entries):
            st.warning("Hay recibos sin pagar. Márcalos como pagados antes de cerrar el período.")

    render_info_card("Alcance", "RRHH básico: empleados, períodos, recibos de pago con neto calculado. No sustituye asesoría contable o legal-laboral.", "RRHH")


app_shell.FUNCTIONAL_MODULES["RRHH y nómina"] = render_payroll
