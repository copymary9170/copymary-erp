"""Gastos y presupuesto con control mensual, alertas y seguimiento."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("expense_records", "Gastos registrados"),
        ("budget_lines", "Presupuestos por categoría"),
        ("expense_approval_requests", "Solicitudes de aprobación de gastos"),
        ("expense_budget_alerts", "Alertas de gastos y presupuesto"),
        ("expense_budget_reviews", "Revisiones de presupuesto"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


CATEGORIES = (
    "Papelería",
    "Tintas y consumibles",
    "Servicios",
    "Transporte",
    "Publicidad",
    "Software",
    "Equipo",
    "Mantenimiento",
    "Comisiones",
    "Personal",
    "Hogar usado por negocio",
    "Otro",
)

PAYMENT_METHODS = ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Punto", "Tarjeta", "Otro")


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, rows: list[dict]) -> None:
    st.session_state[key] = rows


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def _date(value) -> date | None:
    raw = str(value or "")[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _month_key(value: date | None = None) -> str:
    current = value or date.today()
    return f"{current.year:04d}-{current.month:02d}"


def _period_expenses(expenses: list[dict], period: str) -> list[dict]:
    return [row for row in expenses if str(row.get("expense_date", ""))[:7] == period and row.get("status", "Registrado") != "Anulado"]


def _budget_for(category: str, period: str, budgets: list[dict]) -> dict:
    return next((row for row in budgets if row.get("category") == category and row.get("period") == period and row.get("status", "Activo") == "Activo"), {})


def _spent_by_category(expenses: list[dict]) -> dict[str, float]:
    output: dict[str, float] = defaultdict(float)
    for row in expenses:
        output[str(row.get("category", "Otro"))] += _num(row.get("amount"))
    return output


def _append_cash_expense(expense: dict) -> None:
    movements = _rows("cash_movements")
    movements.append({
        "movement_id": uuid4().hex[:10],
        "created_at_utc": _now(),
        "movement_type": "Egreso",
        "category": str(expense.get("category", "Gasto")),
        "amount": _num(expense.get("amount")),
        "payment_method": str(expense.get("payment_method", "Otro")),
        "reference": str(expense.get("expense_id", "")),
        "notes": str(expense.get("description", "")),
        "responsible": str(expense.get("responsible", "Sin asignar")),
        "status": "Aplicado",
        "reversed": False,
    })
    _save("cash_movements", movements)


def _export_expenses(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Fecha", "Categoría", "Descripción", "Monto", "Método", "Responsable", "Estado", "Proveedor", "Referencia"])
    for row in rows:
        writer.writerow([
            row.get("expense_id", ""), row.get("expense_date", ""), row.get("category", ""), row.get("description", ""),
            row.get("amount", 0), row.get("payment_method", ""), row.get("responsible", ""), row.get("status", ""),
            row.get("supplier", ""), row.get("reference", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def _export_budget(period: str, budgets: list[dict], expenses: list[dict]) -> bytes:
    spent = _spent_by_category(_period_expenses(expenses, period))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Periodo", "Categoría", "Presupuesto", "Gastado", "Disponible", "Uso %", "Responsable"])
    for budget in budgets:
        if budget.get("period") != period:
            continue
        amount = _num(budget.get("amount"))
        used = spent.get(str(budget.get("category", "Otro")), 0.0)
        writer.writerow([
            period, budget.get("category", ""), amount, used, amount - used, used / amount * 100 if amount else 0.0, budget.get("responsible", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_expenses_budget_plus() -> None:
    render_page_header(
        "Gastos y presupuesto",
        "Registra gastos, controla presupuesto mensual, aprueba egresos y detecta desviaciones.",
    )

    expenses = _rows("expense_records")
    budgets = _rows("budget_lines")
    requests = _rows("expense_approval_requests")
    alerts = _rows("expense_budget_alerts")
    reviews = _rows("expense_budget_reviews")
    period = _month_key()
    current_expenses = _period_expenses(expenses, period)
    current_spent = sum(_num(row.get("amount")) for row in current_expenses)
    current_budget = sum(_num(row.get("amount")) for row in budgets if row.get("period") == period and row.get("status", "Activo") == "Activo")
    usage = current_spent / current_budget * 100 if current_budget else 0.0
    pending_requests = [row for row in requests if row.get("status") == "Pendiente"]
    overspent_categories = []
    spent_by_category = _spent_by_category(current_expenses)
    for category, spent in spent_by_category.items():
        budget = _budget_for(category, period, budgets)
        if budget and spent > _num(budget.get("amount")):
            overspent_categories.append(category)

    metrics = st.columns(5)
    metrics[0].metric("Gasto del mes", format_money(current_spent, get_currency()))
    metrics[1].metric("Presupuesto", format_money(current_budget, get_currency()))
    metrics[2].metric("Uso", f"{usage:,.1f}%")
    metrics[3].metric("Solicitudes", str(len(pending_requests)))
    metrics[4].metric("Categorías excedidas", str(len(overspent_categories)))

    if current_budget and usage >= 100:
        st.error("El gasto mensual ya superó el presupuesto total.")
    elif current_budget and usage >= 80:
        st.warning("El gasto mensual ya supera 80% del presupuesto.")
    if overspent_categories:
        st.error("Hay categorías que superaron su presupuesto mensual.")

    register_tab, budget_tab, approval_tab, dashboard_tab, review_tab = st.tabs(("Registrar gasto", "Presupuesto", "Aprobaciones", "Dashboard", "Revisión"))

    with register_tab:
        with st.form("expense_record_form", clear_on_submit=True):
            cols = st.columns(5)
            expense_date = cols[0].date_input("Fecha", value=date.today())
            category = cols[1].selectbox("Categoría", CATEGORIES)
            amount = cols[2].number_input("Monto", min_value=0.01, value=1.0, step=1.0)
            payment_method = cols[3].selectbox("Método", PAYMENT_METHODS)
            responsible = cols[4].text_input("Responsable")
            description = st.text_area("Descripción", max_chars=500)
            extra = st.columns(3)
            supplier = extra[0].text_input("Proveedor")
            reference = extra[1].text_input("Referencia")
            business_percent = extra[2].number_input("% uso del negocio", min_value=0.0, max_value=100.0, value=100.0, step=5.0)
            register_cash = st.checkbox("Crear egreso en Caja", value=True)
            requires_approval = st.checkbox("Requiere aprobación antes de registrar", value=False)
            submitted = st.form_submit_button("Guardar gasto", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip() or not description.strip():
                st.error("Responsable y descripción son obligatorios.")
            elif requires_approval:
                requests.append({
                    "request_id": f"EXR-{uuid4().hex[:8].upper()}",
                    "expense_date": expense_date.isoformat(),
                    "category": category,
                    "amount": float(amount),
                    "payment_method": payment_method,
                    "responsible": responsible.strip(),
                    "description": description.strip(),
                    "supplier": supplier.strip(),
                    "reference": reference.strip(),
                    "business_percent": float(business_percent),
                    "status": "Pendiente",
                    "created_at_utc": _now(),
                })
                _save("expense_approval_requests", requests)
                st.rerun()
            else:
                expense = {
                    "expense_id": f"EXP-{uuid4().hex[:8].upper()}",
                    "expense_date": expense_date.isoformat(),
                    "category": category,
                    "amount": float(amount) * float(business_percent) / 100.0,
                    "gross_amount": float(amount),
                    "business_percent": float(business_percent),
                    "payment_method": payment_method,
                    "responsible": responsible.strip(),
                    "description": description.strip(),
                    "supplier": supplier.strip(),
                    "reference": reference.strip(),
                    "status": "Registrado",
                    "created_at_utc": _now(),
                }
                expenses.append(expense)
                _save("expense_records", expenses)
                if register_cash:
                    _append_cash_expense(expense)
                st.rerun()

        filters = st.columns(4)
        period_filter = filters[0].selectbox("Periodo", (period, "Todo"))
        category_filter = filters[1].selectbox("Categoría", ("Todas", *CATEGORIES))
        method_filter = filters[2].selectbox("Método", ("Todos", *PAYMENT_METHODS))
        query = filters[3].text_input("Buscar").strip().casefold()
        visible = []
        for row in expenses:
            text = " ".join(str(row.get(field, "")) for field in ("description", "supplier", "reference", "responsible")).casefold()
            if period_filter != "Todo" and str(row.get("expense_date", ""))[:7] != period_filter:
                continue
            if category_filter != "Todas" and row.get("category") != category_filter:
                continue
            if method_filter != "Todos" and row.get("payment_method") != method_filter:
                continue
            if query and query not in text:
                continue
            visible.append(row)
        st.download_button("Descargar gastos CSV", data=_export_expenses(visible), file_name=f"gastos_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not visible)
        for row in reversed(visible[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row.get('description', 'Gasto')}**")
                cols[0].caption(f"{row.get('expense_date', '')} · {row.get('category', '')} · {row.get('supplier', '')}")
                cols[1].metric("Monto", format_money(_num(row.get("amount")), get_currency()))
                cols[2].metric("Método", str(row.get("payment_method", "")))
                cols[3].metric("Estado", str(row.get("status", "")))

    with budget_tab:
        with st.form("budget_line_form", clear_on_submit=True):
            cols = st.columns(5)
            budget_period = cols[0].text_input("Periodo", value=period, placeholder="YYYY-MM")
            budget_category = cols[1].selectbox("Categoría", CATEGORIES, key="budget_category")
            budget_amount = cols[2].number_input("Presupuesto", min_value=0.0, value=0.0, step=1.0)
            responsible = cols[3].text_input("Responsable")
            alert_percent = cols[4].number_input("Alerta %", min_value=1, max_value=150, value=80, step=5)
            note = st.text_input("Nota")
            submitted = st.form_submit_button("Guardar presupuesto", type="primary", use_container_width=True)
        if submitted:
            if not budget_period.strip() or budget_amount <= 0 or not responsible.strip():
                st.error("Periodo, monto y responsable son obligatorios.")
            else:
                budgets.append({
                    "budget_id": f"BDG-{uuid4().hex[:8].upper()}",
                    "period": budget_period.strip(),
                    "category": budget_category,
                    "amount": float(budget_amount),
                    "alert_percent": int(alert_percent),
                    "responsible": responsible.strip(),
                    "note": note.strip(),
                    "status": "Activo",
                    "created_at_utc": _now(),
                })
                _save("budget_lines", budgets)
                st.rerun()
        st.download_button("Descargar presupuesto CSV", data=_export_budget(period, budgets, expenses), file_name=f"presupuesto_{period}.csv", mime="text/csv", use_container_width=True, disabled=not budgets)
        for budget in reversed([row for row in budgets if row.get("period") == period][-100:]):
            spent = spent_by_category.get(str(budget.get("category", "Otro")), 0.0)
            amount = _num(budget.get("amount"))
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{budget.get('category', '')} · {budget.get('period', '')}**")
                cols[0].caption(f"{budget.get('responsible', '')} · {budget.get('note', '')}")
                cols[1].metric("Presupuesto", format_money(amount, get_currency()))
                cols[2].metric("Gastado", format_money(spent, get_currency()))
                cols[3].metric("Uso", f"{spent / amount * 100 if amount else 0:,.1f}%")
                if amount and spent >= amount * _num(budget.get("alert_percent"), 80) / 100.0:
                    st.warning("Esta categoría alcanzó el umbral de alerta.")

    with approval_tab:
        if not pending_requests:
            st.info("No hay solicitudes de gasto pendientes.")
        for request in reversed(pending_requests):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{request.get('request_id', '')} · {request.get('description', '')}**")
                cols[0].caption(f"{request.get('category', '')} · {request.get('responsible', '')} · {request.get('expense_date', '')}")
                cols[1].metric("Monto", format_money(_num(request.get("amount")), get_currency()))
                cols[2].metric("Método", str(request.get("payment_method", "")))
                with st.form(f"approve_expense_{request.get('request_id')}"):
                    decision = st.selectbox("Decisión", ("Aprobar", "Rechazar"), key=f"decision_{request.get('request_id')}")
                    approved_by = st.text_input("Responsable de decisión", key=f"approver_{request.get('request_id')}")
                    note = st.text_area("Nota", max_chars=400, key=f"note_{request.get('request_id')}")
                    submitted = st.form_submit_button("Guardar decisión", type="primary", use_container_width=True)
                if submitted:
                    if not approved_by.strip():
                        st.error("Indica responsable de decisión.")
                    else:
                        changed = []
                        for row in requests:
                            current = dict(row)
                            if current.get("request_id") == request.get("request_id"):
                                current["status"] = "Aprobada" if decision == "Aprobar" else "Rechazada"
                                current["approved_by"] = approved_by.strip() if decision == "Aprobar" else ""
                                current["decision_note"] = note.strip()
                                current["decision_at_utc"] = _now()
                            changed.append(current)
                        _save("expense_approval_requests", changed)
                        if decision == "Aprobar":
                            expense = {
                                "expense_id": f"EXP-{uuid4().hex[:8].upper()}",
                                "expense_date": str(request.get("expense_date", date.today().isoformat())),
                                "category": str(request.get("category", "Otro")),
                                "amount": _num(request.get("amount")) * _num(request.get("business_percent"), 100.0) / 100.0,
                                "gross_amount": _num(request.get("amount")),
                                "business_percent": _num(request.get("business_percent"), 100.0),
                                "payment_method": str(request.get("payment_method", "Otro")),
                                "responsible": approved_by.strip(),
                                "description": str(request.get("description", "")),
                                "supplier": str(request.get("supplier", "")),
                                "reference": str(request.get("reference", "")),
                                "status": "Registrado",
                                "source_request_id": str(request.get("request_id", "")),
                                "created_at_utc": _now(),
                            }
                            expenses.append(expense)
                            _save("expense_records", expenses)
                            _append_cash_expense(expense)
                        st.rerun()

    with dashboard_tab:
        st.markdown("#### Uso por categoría")
        for category in CATEGORIES:
            spent = spent_by_category.get(category, 0.0)
            budget = _budget_for(category, period, budgets)
            amount = _num(budget.get("amount")) if budget else 0.0
            if spent == 0 and amount == 0:
                continue
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{category}**")
                cols[1].metric("Presupuesto", format_money(amount, get_currency()))
                cols[2].metric("Gastado", format_money(spent, get_currency()))
                cols[3].metric("Disponible", format_money(amount - spent, get_currency()))
        st.markdown("#### Alertas")
        generated_alerts = []
        for budget in budgets:
            if budget.get("period") != period or budget.get("status", "Activo") != "Activo":
                continue
            amount = _num(budget.get("amount"))
            spent = spent_by_category.get(str(budget.get("category", "Otro")), 0.0)
            threshold = amount * _num(budget.get("alert_percent"), 80) / 100.0
            if amount and spent >= threshold:
                generated_alerts.append({"category": budget.get("category"), "spent": spent, "budget": amount, "alert_percent": budget.get("alert_percent", 80)})
        if not generated_alerts:
            st.success("No hay alertas de presupuesto para el periodo actual.")
        for alert in generated_alerts:
            st.warning(f"{alert['category']}: {format_money(alert['spent'], get_currency())} de {format_money(alert['budget'], get_currency())} usado.")
        if generated_alerts and st.button("Guardar alertas del periodo", use_container_width=True):
            for alert in generated_alerts:
                alerts.append({
                    "alert_id": f"BDA-{uuid4().hex[:8].upper()}",
                    "period": period,
                    **alert,
                    "created_at_utc": _now(),
                })
            _save("expense_budget_alerts", alerts)
            st.rerun()

    with review_tab:
        with st.form("expense_budget_review_form", clear_on_submit=True):
            reviewer = st.text_input("Revisado por")
            status = st.selectbox("Resultado", ("En control", "Requiere ajuste", "Presupuesto excedido"))
            conclusion = st.text_area("Conclusión", max_chars=700)
            submitted = st.form_submit_button("Guardar revisión mensual", type="primary", use_container_width=True)
        if submitted:
            if not reviewer.strip() or not conclusion.strip():
                st.error("Revisor y conclusión son obligatorios.")
            else:
                reviews.append({
                    "review_id": f"BDR-{uuid4().hex[:8].upper()}",
                    "period": period,
                    "spent": current_spent,
                    "budget": current_budget,
                    "usage_percent": usage,
                    "status": status,
                    "reviewer": reviewer.strip(),
                    "conclusion": conclusion.strip(),
                    "created_at_utc": _now(),
                })
                _save("expense_budget_reviews", reviews)
                st.rerun()
        if not reviews:
            st.info("No hay revisiones guardadas.")
        for review in reversed(reviews[-50:]):
            st.write(f"**{review.get('review_id', '')} · {review.get('period', '')} · {review.get('status', '')}** — {review.get('reviewer', '')}: {review.get('conclusion', '')}")

    render_info_card(
        "Gasto bajo control",
        "Los gastos se comparan contra presupuesto, pueden requerir aprobación y dejan evidencia mensual para decisiones.",
        "CONTROL FINANCIERO",
    )


app_shell.FUNCTIONAL_MODULES["Gastos y presupuesto"] = render_expenses_budget_plus
