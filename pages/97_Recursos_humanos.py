"""Recursos Humanos: asistencia, vacaciones/permisos y prestaciones sociales.

Página autocontenida (Streamlit multipágina): se activa solo con colocarla en
`pages/`; no requiere cablear app.py ni la navegación.

- Asistencia: registro de horas/estado por empleado y día.
- Vacaciones y permisos: solicitudes con rango de fechas y estado.
- Prestaciones sociales: estimación referencial (LOTTT) según fecha de ingreso
  y salario mensual.

Toma la lista de empleados de `team_members` si existe; guarda datos propios en
`hr_attendance`, `hr_leaves` y `hr_employee_meta`, y suma esas secciones al
respaldo general si está disponible. Lectura defensiva.

AVISO: la estimación de prestaciones es referencial y NO sustituye el cálculo
legal formal.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

import streamlit as st

try:
    from src.session_utils import read_list as _read_list, save_list as _save_list
except Exception:  # pragma: no cover
    def _read_list(key: str) -> list[dict]:
        value = st.session_state.get(key, [])
        return value if isinstance(value, list) else []

    def _save_list(key: str, rows: list[dict]) -> None:
        st.session_state[key] = rows


ATTENDANCE_KEY = "hr_attendance"
LEAVES_KEY = "hr_leaves"
META_KEY = "hr_employee_meta"

ATTEND_STATUS = ("Presente", "Ausente", "Tarde", "Reposo", "Permiso")
LEAVE_TYPES = ("Vacaciones", "Permiso remunerado", "Permiso no remunerado", "Reposo médico")
LEAVE_STATUS = ("Solicitada", "Aprobada", "Rechazada")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(row: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _register_backup() -> None:
    try:
        from src import session_backup
        labels = {ATTENDANCE_KEY: "RR. HH. — asistencia",
                  LEAVES_KEY: "RR. HH. — vacaciones/permisos",
                  META_KEY: "RR. HH. — datos de empleados"}
        changed = False
        for key, label in labels.items():
            if key not in session_backup.LIST_SECTIONS:
                session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, key)
                session_backup.SECTION_LABELS[key] = label
                changed = True
        if changed:
            session_backup.SESSION_KEYS = (
                "general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS,
            )
    except Exception:
        pass


def _employees() -> list[str]:
    names = []
    for row in _read_list("team_members"):
        name = str(_first(row, "name", "nombre", "member_name", default="")).strip()
        if name and name not in names:
            names.append(name)
    for row in _read_list(META_KEY):
        name = str(row.get("name", "")).strip()
        if name and name not in names:
            names.append(name)
    return names


def _team_member(name: str) -> dict:
    for row in _read_list("team_members"):
        if str(_first(row, "name", "nombre", "member_name", default="")).strip() == name:
            return row
    return {}


def _meta(name: str) -> dict:
    for row in _read_list(META_KEY):
        if str(row.get("name", "")).strip() == name:
            return row
    return {}


def _save_meta(name: str, hire_date: str, monthly_salary: float) -> None:
    rows = _read_list(META_KEY)
    found = False
    for row in rows:
        if str(row.get("name", "")).strip() == name:
            row.update({"hire_date": hire_date, "monthly_salary": monthly_salary,
                        "updated_at_utc": _now()})
            found = True
    if not found:
        rows.append({"name": name, "hire_date": hire_date, "monthly_salary": monthly_salary,
                     "created_at_utc": _now()})
    _save_list(META_KEY, rows)


def estimate_severance(hire: date | None, monthly_salary: float, today: date | None = None) -> dict:
    """Estimación referencial de prestaciones sociales (garantía trimestral de
    15 días por trimestre + 2 días adicionales por año a partir del 2º año,
    tope 30). NO sustituye el cálculo legal."""
    today = today or date.today()
    if hire is None or monthly_salary <= 0 or hire > today:
        return {"months": 0, "quarters": 0, "days": 0.0, "amount": 0.0}
    months = (today.year - hire.year) * 12 + (today.month - hire.month)
    quarters = months // 3
    guarantee_days = quarters * 15
    years = months // 12
    additional_days = 0
    for year in range(2, years + 2):  # 2 días/año desde el 2º año
        if year <= years + 1:
            additional_days += min(2 * (year - 1), 30)
    additional_days = min(additional_days, 30) if years >= 1 else 0
    total_days = guarantee_days + additional_days
    daily = monthly_salary / 30.0
    return {"months": months, "quarters": quarters, "days": float(total_days),
            "amount": round(total_days * daily, 2)}


def render() -> None:
    _register_backup()
    st.title("Recursos Humanos")
    st.caption("Asistencia, vacaciones/permisos y estimación de prestaciones sociales.")

    employees = _employees()
    if not employees:
        st.info("No hay empleados en 'team_members'. Agrega uno aquí para empezar.")
        with st.form("hr_add_employee", clear_on_submit=True):
            new_name = st.text_input("Nombre del empleado")
            if st.form_submit_button("Agregar empleado", type="primary") and new_name.strip():
                _save_meta(new_name.strip(), "", 0.0)
                st.rerun()
        return

    tab_att, tab_leave, tab_sev = st.tabs(
        ("🕒 Asistencia", "🌴 Vacaciones y permisos", "💼 Prestaciones sociales"))

    with tab_att:
        with st.form("hr_attendance_form", clear_on_submit=True):
            cols = st.columns(4)
            employee = cols[0].selectbox("Empleado", employees, key="att_emp")
            day = cols[1].date_input("Fecha", value=date.today())
            status = cols[2].selectbox("Estado", ATTEND_STATUS)
            hours = cols[3].number_input("Horas", min_value=0.0, max_value=24.0, value=8.0, step=0.5)
            note = st.text_input("Nota", max_chars=120)
            if st.form_submit_button("Registrar asistencia", type="primary", use_container_width=True):
                rows = _read_list(ATTENDANCE_KEY)
                rows.append({"id": uuid4().hex[:8].upper(), "name": employee,
                             "date": day.isoformat(), "status": status,
                             "hours": float(hours), "note": note.strip(),
                             "created_at_utc": _now()})
                _save_list(ATTENDANCE_KEY, rows)
                st.success("Asistencia registrada.")
                st.rerun()
        today = date.today()
        summary: dict[str, float] = {}
        for row in _read_list(ATTENDANCE_KEY):
            d = _parse_date(row.get("date"))
            if d and d.year == today.year and d.month == today.month and str(row.get("status")) == "Presente":
                summary[row.get("name", "")] = summary.get(row.get("name", ""), 0.0) + _num(row.get("hours"))
        if summary:
            st.subheader("Horas presentes este mes")
            st.dataframe([{"Empleado": k, "Horas": round(v, 1)} for k, v in summary.items()],
                         use_container_width=True, hide_index=True)

    with tab_leave:
        with st.form("hr_leave_form", clear_on_submit=True):
            cols = st.columns(4)
            employee = cols[0].selectbox("Empleado", employees, key="leave_emp")
            leave_type = cols[1].selectbox("Tipo", LEAVE_TYPES)
            start = cols[2].date_input("Desde", value=date.today())
            end = cols[3].date_input("Hasta", value=date.today())
            reason = st.text_input("Motivo", max_chars=120)
            if st.form_submit_button("Registrar solicitud", type="primary", use_container_width=True):
                if end < start:
                    st.error("La fecha 'Hasta' no puede ser anterior a 'Desde'.")
                else:
                    days = (end - start).days + 1
                    rows = _read_list(LEAVES_KEY)
                    rows.append({"id": uuid4().hex[:8].upper(), "name": employee,
                                 "type": leave_type, "start": start.isoformat(),
                                 "end": end.isoformat(), "days": days, "status": "Solicitada",
                                 "reason": reason.strip(), "created_at_utc": _now()})
                    _save_list(LEAVES_KEY, rows)
                    st.success(f"Solicitud registrada ({days} día[s]).")
                    st.rerun()
        leaves = _read_list(LEAVES_KEY)
        if leaves:
            st.subheader("Solicitudes")
            for leave in reversed(leaves[-30:]):
                with st.container(border=True):
                    cols = st.columns([3, 1, 1])
                    cols[0].markdown(f"**{leave.get('name')}** · {leave.get('type')}")
                    cols[0].caption(f"{leave.get('start')} → {leave.get('end')} "
                                    f"({leave.get('days')} día[s]) · {leave.get('status')}")
                    if leave.get("status") == "Solicitada":
                        if cols[1].button("Aprobar", key=f"leave_ok_{leave['id']}", use_container_width=True):
                            for row in leaves:
                                if row.get("id") == leave["id"]:
                                    row["status"] = "Aprobada"
                            _save_list(LEAVES_KEY, leaves)
                            st.rerun()
                        if cols[2].button("Rechazar", key=f"leave_no_{leave['id']}", use_container_width=True):
                            for row in leaves:
                                if row.get("id") == leave["id"]:
                                    row["status"] = "Rechazada"
                            _save_list(LEAVES_KEY, leaves)
                            st.rerun()

    with tab_sev:
        st.caption("Estimación referencial (LOTTT). Ajusta fecha de ingreso y salario si faltan.")
        employee = st.selectbox("Empleado", employees, key="sev_emp")
        member = _team_member(employee)
        meta = _meta(employee)
        hire_default = _parse_date(_first(meta, "hire_date", default=None)
                                   or _first(member, "hire_date", "fecha_ingreso", default=None)) or date.today()
        salary_default = _num(_first(meta, "monthly_salary", default=None)
                              or _first(member, "monthly_salary", "salary", "sueldo", default=0.0))
        cols = st.columns(3)
        hire = cols[0].date_input("Fecha de ingreso", value=hire_default, key="sev_hire")
        salary = cols[1].number_input("Salario mensual", min_value=0.0, value=float(salary_default),
                                      step=1.0, key="sev_salary")
        if cols[2].button("Guardar datos del empleado", use_container_width=True):
            _save_meta(employee, hire.isoformat(), float(salary))
            st.success("Datos guardados.")
            st.rerun()
        est = estimate_severance(hire, float(salary))
        metrics = st.columns(4)
        metrics[0].metric("Meses", str(est["months"]))
        metrics[1].metric("Trimestres", str(est["quarters"]))
        metrics[2].metric("Días acumulados (est.)", f"{est['days']:.0f}")
        metrics[3].metric("Monto estimado", f"{est['amount']:,.2f}")
        st.caption("Estimación referencial; no sustituye el cálculo legal formal de prestaciones.")


render()
