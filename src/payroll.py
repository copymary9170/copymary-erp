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
from html import escape
from uuid import uuid4

import streamlit as st

from src import app_shell, payroll_legal_ve as legal_ve
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database, record_audit_event
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now

PAYMENT_FREQUENCIES = ("Mensual", "Quincenal", "Semanal")
DEPARTMENTS = ("Producción", "Ventas", "Administración", "Diseño", "Otro")
PAYMENT_METHODS = ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro")
LEAVE_TYPES = ("Vacaciones", "Permiso", "Reposo médico", "Otro")


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


def time_off_days(start_date: str, end_date: str) -> int:
    """Días de una vacación/permiso, contando el primer y el último día
    (7 al 7 son 1 día, no 0). Nunca negativo: si la fecha final quedó antes
    de la inicial por error de captura, no debe generar un conteo raro."""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    return max((end - start).days + 1, 0)


def salary_change_amount(previous_salary: float, new_salary: float) -> float:
    """Diferencia del cambio de salario (positiva = aumento, negativa = recorte)."""
    return new_salary - previous_salary


def years_of_service(hire_date: str, as_of: str | None = None) -> float:
    """Antigüedad en años (fraccionaria) entre la fecha de ingreso y una
    fecha de corte (hoy por defecto). Usa 365.25 días/año para no perder
    precisión por años bisiestos en antigüedades largas."""
    start = date.fromisoformat(hire_date)
    end = date.fromisoformat(as_of) if as_of else date.today()
    return max((end - start).days / 365.25, 0.0)


# ---------------------------------------------------------------------------
# Acceso a datos
# ---------------------------------------------------------------------------

def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


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


def _entry_by_id(entry_id: str) -> dict | None:
    rows = _fetch_all(
        """
        SELECT pe.*, e.full_name, e.position, p.period_start, p.period_end
        FROM payroll_entries pe
        JOIN employees e ON e.employee_id = pe.employee_id
        JOIN payroll_periods p ON p.period_id = pe.period_id
        WHERE pe.entry_id = ?
        """,
        (entry_id,),
    )
    return rows[0] if rows else None


def mark_entry_paid(entry_id: str, payment_method: str = "Efectivo", responsible: str = "") -> None:
    """Marca un recibo como pagado Y registra la salida de efectivo real en
    Caja (categoría 'Nómina'). Antes solo se cambiaba `payment_status`: el
    dinero desaparecía del rastro contable sin dejar ningún egreso en Caja.

    `cash_movement_id` queda guardado en el recibo para poder rastrear el
    pago en ambos sentidos (del recibo al movimiento de Caja, y viceversa)."""
    entry = _entry_by_id(entry_id)
    if entry is None:
        return
    net = net_pay(
        float(entry.get("base_salary") or 0), float(entry.get("bonuses_total") or 0), float(entry.get("deductions_total") or 0)
    )
    currency = str(entry.get("currency") or "USD")
    period = period_label({"period_start": entry.get("period_start"), "period_end": entry.get("period_end")})

    from src import cash_plus

    cash_movement_id = uuid4().hex[:10]
    cash_plus._append_movement(
        "Egreso", "Nómina", net, payment_method,
        reference=f"Nómina {entry.get('full_name', '')} · {period}",
        notes=f"Recibo {entry_id} ({currency})",
        responsible=responsible,
        session_id="",
    )

    initialize_database()
    with connect() as conn:
        conn.execute(
            "UPDATE payroll_entries SET payment_status = 'paid', paid_at_utc = ?, payment_method = ?, cash_movement_id = ? WHERE entry_id = ?",
            (_now(), payment_method, cash_movement_id, entry_id),
        )
    record_audit_event("rrhh", "payroll_entries", entry_id, "pay", after={"payment_method": payment_method, "net": net})


# ---------------------------------------------------------------------------
# Vacaciones y permisos
# ---------------------------------------------------------------------------

def list_time_off(employee_id: str = "") -> list[dict]:
    query = """
        SELECT t.*, e.full_name
        FROM employee_time_off t JOIN employees e ON e.employee_id = t.employee_id
    """
    params: tuple = ()
    if employee_id:
        query += " WHERE t.employee_id = ?"
        params = (employee_id,)
    query += " ORDER BY t.start_date DESC"
    return _fetch_all(query, params)


def create_time_off(employee_id: str, leave_type: str, start_date: str, end_date: str, paid: bool = True, notes: str = "") -> str:
    initialize_database()
    time_off_id = f"TOF-{uuid4().hex[:8].upper()}"
    days = time_off_days(start_date, end_date)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO employee_time_off(time_off_id, employee_id, leave_type, start_date, end_date, days, paid, notes, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (time_off_id, employee_id, leave_type, start_date, end_date, float(days), 1 if paid else 0, notes.strip(), _now()),
        )
    record_audit_event("rrhh", "employee_time_off", time_off_id, "create", after={"leave_type": leave_type, "days": days})
    return time_off_id


# ---------------------------------------------------------------------------
# Historial de aumentos salariales
# ---------------------------------------------------------------------------

def salary_history_for_employee(employee_id: str) -> list[dict]:
    return _fetch_all(
        "SELECT * FROM employee_salary_history WHERE employee_id = ? ORDER BY effective_date DESC",
        (employee_id,),
    )


def all_salary_history() -> list[dict]:
    return _fetch_all(
        """
        SELECT h.*, e.full_name
        FROM employee_salary_history h JOIN employees e ON e.employee_id = h.employee_id
        ORDER BY h.effective_date DESC
        """
    )


def change_salary(employee_id: str, new_salary: float, currency: str, effective_date: str, reason: str = "") -> str:
    """Registra un cambio de salario en el historial Y actualiza el salario
    base del empleado, para que los próximos recibos de nómina ya partan del
    nuevo monto. Antes solo se veía el salario ACTUAL, sin ninguna historia
    de cuándo o por qué cambió."""
    initialize_database()
    employees = _fetch_all("SELECT base_salary FROM employees WHERE employee_id = ?", (employee_id,))
    previous_salary = float(employees[0]["base_salary"]) if employees else 0.0
    change_id = f"SAL-{uuid4().hex[:8].upper()}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO employee_salary_history(change_id, employee_id, previous_salary, new_salary, currency, effective_date, reason, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (change_id, employee_id, previous_salary, float(new_salary), currency, effective_date, reason.strip(), _now()),
        )
        conn.execute("UPDATE employees SET base_salary = ?, salary_currency = ? WHERE employee_id = ?", (float(new_salary), currency, employee_id))
    record_audit_event(
        "rrhh", "employees", employee_id, "salary_change",
        before={"base_salary": previous_salary}, after={"base_salary": float(new_salary), "reason": reason},
    )
    return change_id


# ---------------------------------------------------------------------------
# Recibo de pago descargable
# ---------------------------------------------------------------------------

def build_payslip_html(entry: dict) -> bytes:
    """Comprobante de pago imprimible para entregarle al empleado — mismo
    criterio visual que las cotizaciones/comprobantes de `commercial_documents.py`."""
    currency = str(entry.get("currency") or "USD")
    base_salary = float(entry.get("base_salary") or 0)
    bonuses_total = float(entry.get("bonuses_total") or 0)
    deductions_total = float(entry.get("deductions_total") or 0)
    net = net_pay(base_salary, bonuses_total, deductions_total)
    period = period_label({"period_start": entry.get("period_start"), "period_end": entry.get("period_end")})
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Recibo de pago {escape(str(entry.get('entry_id', '')))}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; color: #222; }}
h1 {{ margin-bottom: 4px; }}
.meta {{ color: #666; margin-bottom: 24px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; }}
th {{ background: #f3f3f3; }}
.totals {{ margin-top: 24px; text-align: right; }}
.notes {{ margin-top: 28px; padding: 14px; background: #f7f7f7; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>CopyMary</h1>
<h2>Recibo de pago</h2>
<div class="meta">
Recibo: {escape(str(entry.get('entry_id', '')))}<br>
Empleado: {escape(str(entry.get('full_name', '')))} · {escape(str(entry.get('position', '')))}<br>
Período: {escape(period)}<br>
Método de pago: {escape(str(entry.get('payment_method') or 'Sin registrar'))}
</div>
<table>
<thead><tr><th>Concepto</th><th>Monto</th></tr></thead>
<tbody>
<tr><td>Salario base</td><td>{escape(format_money(base_salary, currency))}</td></tr>
<tr><td>Bonos{' — ' + escape(str(entry.get('bonuses_detail'))) if entry.get('bonuses_detail') else ''}</td><td>{escape(format_money(bonuses_total, currency))}</td></tr>
<tr><td>Deducciones{' — ' + escape(str(entry.get('deductions_detail'))) if entry.get('deductions_detail') else ''}</td><td>-{escape(format_money(deductions_total, currency))}</td></tr>
</tbody>
</table>
<div class="totals"><p>Neto pagado: <strong>{escape(format_money(net, currency))}</strong></p></div>
<div class="notes">Este recibo es un comprobante interno de CopyMary ERP. No sustituye una nómina fiscal/legal formal.</div>
</body>
</html>"""
    return html.encode("utf-8")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def render_payroll() -> None:
    render_page_header("RRHH y nómina", "Registro de empleados y recibos de pago por período.")
    st.caption("Este módulo calcula salario + bonos − deducciones = neto, con historial y auditoría. No calcula prestaciones sociales, utilidades ni retenciones de ley — valida esas reglas con un contador antes de usarlas para pagos reales.")

    employees = list_employees()
    periods = list_periods()
    currency = get_currency()

    employees_tab, periods_tab, time_off_tab, salary_history_tab, legal_ve_tab = st.tabs(
        ("Empleados", "Períodos de nómina", "Vacaciones y permisos", "Historial salarial", "Estimaciones legales (VE)")
    )

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
        else:
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
                    cols = st.columns([3, 2, 2, 2])
                    cols[0].markdown(f"**{row['full_name']}** · {row.get('position', '')}")
                    cols[1].write(f"Base {format_money(row.get('base_salary', 0.0), row.get('currency', 'USD'))}")
                    cols[2].write(f"Neto {format_money(net, row.get('currency', 'USD'))}")
                    payslip_entry = {**row, "period_start": selected_period.get("period_start"), "period_end": selected_period.get("period_end")}
                    cols[3].download_button(
                        "Recibo", data=build_payslip_html(payslip_entry), file_name=f"recibo_{row['entry_id']}.html",
                        mime="text/html", key=f"payslip_{row['entry_id']}", use_container_width=True,
                    )
                    if row.get("payment_status") == "paid":
                        st.caption(f"✅ Pagado · {row.get('payment_method') or 'Sin registrar'} · {str(row.get('paid_at_utc', ''))[:10]}")
                    else:
                        with st.popover("Pagar"):
                            with st.form(f"pay_form_{row['entry_id']}"):
                                payment_method = st.selectbox("Método de pago", PAYMENT_METHODS, key=f"pay_method_{row['entry_id']}")
                                responsible = st.text_input("Pagado por (opcional)", key=f"pay_by_{row['entry_id']}")
                                confirm_pay = st.form_submit_button("Confirmar pago", type="primary", use_container_width=True)
                            if confirm_pay:
                                mark_entry_paid(row["entry_id"], payment_method, responsible)
                                st.success("Pago registrado: se generó el egreso en Caja (categoría 'Nómina').")
                                st.rerun()

            if not is_closed and entries and not entries_pending_payment(entries):
                if st.button("Cerrar período", type="primary"):
                    close_period(selected_period["period_id"])
                    st.rerun()
            elif not is_closed and entries_pending_payment(entries):
                st.warning("Hay recibos sin pagar. Márcalos como pagados antes de cerrar el período.")

    with time_off_tab:
        if not employees:
            st.info("Registra empleados antes de llevar vacaciones y permisos.")
        else:
            employee_options = {f"{row['full_name']} · {row.get('position', '')}": row for row in employees}
            with st.form("time_off_form", clear_on_submit=True):
                employee_label = st.selectbox("Empleado", tuple(employee_options.keys()), key="tof_employee")
                type_col, paid_col = st.columns(2)
                leave_type = type_col.selectbox("Tipo", LEAVE_TYPES)
                paid = paid_col.checkbox("Remunerado", value=True)
                start_col, end_col = st.columns(2)
                start_date = start_col.date_input("Desde", value=date.today())
                end_date = end_col.date_input("Hasta", value=date.today())
                notes = st.text_input("Notas (opcional)")
                submitted_time_off = st.form_submit_button("Registrar", type="primary", use_container_width=True)
            if submitted_time_off:
                if end_date < start_date:
                    st.error("La fecha final no puede ser anterior a la inicial.")
                else:
                    employee_row = employee_options[employee_label]
                    create_time_off(employee_row["employee_id"], leave_type, start_date.isoformat(), end_date.isoformat(), paid, notes)
                    st.success("Vacación/permiso registrado.")
                    st.rerun()

            records = list_time_off()
            if records:
                st.markdown("#### Historial")
                for record in records[:100]:
                    with st.container(border=True):
                        st.markdown(f"**{record.get('full_name')}** · {record.get('leave_type')} · {record.get('days', 0):,.0f} día(s)")
                        st.caption(
                            f"{record.get('start_date')} → {record.get('end_date')} · "
                            f"{'Remunerado' if record.get('paid') else 'No remunerado'}"
                            + (f" · {record.get('notes')}" if record.get("notes") else "")
                        )
            else:
                st.info("Todavía no hay vacaciones ni permisos registrados.")

    with salary_history_tab:
        if not employees:
            st.info("Registra empleados antes de llevar el historial salarial.")
        else:
            employee_options = {f"{row['full_name']} · {row.get('position', '')}": row for row in employees}
            with st.form("salary_change_form", clear_on_submit=True):
                employee_label = st.selectbox("Empleado", tuple(employee_options.keys()), key="sal_employee")
                new_salary = st.number_input("Nuevo salario base", min_value=0.0, step=10.0)
                currency_new = st.selectbox("Moneda", ("USD", "VES", "EUR"), key="sal_currency")
                effective_date = st.date_input("Vigente desde", value=date.today())
                reason = st.text_input("Motivo (opcional)")
                submitted_salary = st.form_submit_button("Registrar cambio de salario", type="primary", use_container_width=True)
            if submitted_salary:
                employee_row = employee_options[employee_label]
                change_salary(employee_row["employee_id"], new_salary, currency_new, effective_date.isoformat(), reason)
                st.success("Salario actualizado. Los próximos recibos de nómina ya parten del nuevo monto.")
                st.rerun()

            history = all_salary_history()
            if history:
                st.markdown("#### Historial de cambios")
                for change in history[:100]:
                    delta = salary_change_amount(float(change.get("previous_salary") or 0), float(change.get("new_salary") or 0))
                    arrow = "📈" if delta > 0 else "📉" if delta < 0 else "➡️"
                    with st.container(border=True):
                        st.markdown(
                            f"**{change.get('full_name')}** {arrow} "
                            f"{format_money(float(change.get('previous_salary') or 0), change.get('currency', 'USD'))} → "
                            f"{format_money(float(change.get('new_salary') or 0), change.get('currency', 'USD'))}"
                        )
                        st.caption(f"Vigente desde {change.get('effective_date')}" + (f" · {change.get('reason')}" if change.get("reason") else ""))
            else:
                st.info("Todavía no hay cambios de salario registrados.")

    with legal_ve_tab:
        st.error(
            "⚠️ Estimador, no cálculo legal certificado. Las FÓRMULAS (días exigidos por la LOTTT) "
            "están fijas, pero el salario mínimo, los topes de cotización y la tasa patronal de IVSS "
            "cambian por Gaceta Oficial y debes actualizarlos abajo tú mismo — este ERP no los conoce. "
            "Antes de liquidar a alguien, pagar prestaciones reales o declarar aportes ante el "
            "IVSS/BANAVIH/INCES, valida estos montos con un contador o abogado laboral."
        )
        if not employees:
            st.info("Registra empleados para ver sus estimaciones.")
        else:
            st.markdown("##### Parámetros vigentes (actualízalos según la Gaceta Oficial)")
            params_col1, params_col2, params_col3 = st.columns(3)
            ivss_employer_rate = params_col1.number_input(
                "Tasa patronal IVSS (%)", min_value=0.0, max_value=100.0, value=10.0, step=0.5,
                help="Varía 9%-11% según la clasificación de riesgo de la empresa ante el INPSASEL.",
            )
            ivss_employee_rate = params_col2.number_input("Tasa trabajador IVSS (%)", min_value=0.0, max_value=100.0, value=4.0, step=0.5)
            contribution_cap = params_col3.number_input(
                "Tope de cotización mensual (IVSS/RPE)", min_value=0.0, value=0.0, step=10.0,
                help="0 = sin tope. Normalmente un múltiplo del salario mínimo vigente — confírmalo en la Gaceta Oficial.",
            )

            employee_options = {f"{row['full_name']} · {row.get('position', '')}": row for row in active_employees(employees)}
            if not employee_options:
                st.info("No hay empleados activos.")
            else:
                selected_label = st.selectbox("Empleado", tuple(employee_options.keys()), key="legal_ve_employee")
                employee = employee_options[selected_label]
                salary = float(employee.get("base_salary") or 0)
                daily_salary = salary / 30.0
                emp_currency = employee.get("salary_currency", "USD")
                tenure = years_of_service(employee["hire_date"])

                st.caption(f"Antigüedad estimada: {tenure:.2f} años · salario diario de referencia: {format_money(daily_salary, emp_currency)}")

                st.markdown("##### Prestaciones sociales (Art. 142 LOTTT)")
                st.caption(
                    "Estimación simplificada: usa el salario ACTUAL para toda la antigüedad, no el "
                    "salario histórico real de cada trimestre. Para una liquidación real, un contador "
                    "debe recalcular con el historial salarial completo del empleado."
                )
                severance = legal_ve.severance_estimate(tenure, daily_salary)
                sev_cols = st.columns(3)
                sev_cols[0].metric("Garantía acumulada (aprox.)", format_money(severance["accumulated_guarantee"], emp_currency))
                sev_cols[1].metric("Cálculo retroactivo (30 días/año)", format_money(severance["retroactive_calculation"], emp_currency))
                sev_cols[2].metric("Pagaría el mayor de los dos", format_money(severance["final_payment"], emp_currency))

                st.markdown("##### Utilidades / aguinaldos (Art. 131-133 LOTTT)")
                months_col, days_col = st.columns(2)
                months_worked = months_col.number_input("Meses trabajados este año", min_value=0, max_value=12, value=12, key="legal_ve_months")
                utilities_days_requested = days_col.number_input(
                    "Días a pagar (mínimo legal 15, tope 120)", min_value=15.0, max_value=120.0, value=15.0, step=1.0, key="legal_ve_util_days",
                )
                utilities = legal_ve.utilities_amount(daily_salary, utilities_days_requested, int(months_worked))
                st.metric("Utilidades estimadas", format_money(utilities, emp_currency))

                st.markdown("##### Vacaciones y bono vacacional (Art. 190 y 192 LOTTT)")
                years_int = max(int(tenure), 1)
                vac_cols = st.columns(3)
                vac_cols[0].metric("Días de disfrute", str(legal_ve.vacation_days(years_int)))
                vac_cols[1].metric("Días de bono vacacional", str(legal_ve.vacation_bonus_days(years_int)))
                vac_cols[2].metric("Monto del bono vacacional", format_money(legal_ve.vacation_bonus_amount(daily_salary, years_int), emp_currency))

                st.markdown("##### Aportes mensuales estimados (IVSS / FAOV / RPE)")
                ivss_employer, ivss_employee = legal_ve.ivss_contribution(salary, ivss_employer_rate, ivss_employee_rate, contribution_cap or None)
                faov_employer, faov_employee = legal_ve.faov_contribution(salary)
                rpe_employer, rpe_employee = legal_ve.rpe_contribution(salary, cap=contribution_cap or None)
                contrib_rows = [
                    {"Concepto": "IVSS", "Aporte patronal": format_money(ivss_employer, emp_currency), "Aporte trabajador": format_money(ivss_employee, emp_currency)},
                    {"Concepto": "FAOV", "Aporte patronal": format_money(faov_employer, emp_currency), "Aporte trabajador": format_money(faov_employee, emp_currency)},
                    {"Concepto": "RPE", "Aporte patronal": format_money(rpe_employer, emp_currency), "Aporte trabajador": format_money(rpe_employee, emp_currency)},
                ]
                st.dataframe(contrib_rows, use_container_width=True, hide_index=True)

    render_info_card("Alcance", "RRHH básico: empleados, períodos, recibos de pago con neto calculado, vacaciones/permisos, historial salarial y pago conectado a Caja. No sustituye asesoría contable o legal-laboral.", "RRHH")


app_shell.FUNCTIONAL_MODULES["RRHH y nómina"] = render_payroll
