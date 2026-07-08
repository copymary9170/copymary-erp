"""Control avanzado para gastos, compromisos y presupuesto."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, expenses_budget_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("expense_recurring_rules", "Gastos recurrentes"),
        ("expense_commitments", "Compromisos de gasto"),
        ("budget_forecasts", "Pronósticos de presupuesto"),
        ("budget_savings_actions", "Acciones de ahorro presupuestario"),
        ("expense_supplier_summary", "Resumen de gastos por proveedor"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


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


def _month_key(value: date | None = None) -> str:
    return base._month_key(value)


def _period_expenses(expenses: list[dict], period: str) -> list[dict]:
    return base._period_expenses(expenses, period)


def _spent_by_category(expenses: list[dict]) -> dict[str, float]:
    return base._spent_by_category(expenses)


def _budget_for(category: str, period: str, budgets: list[dict]) -> dict:
    return base._budget_for(category, period, budgets)


def _month_progress() -> float:
    today = date.today()
    next_month = date(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1)
    days_in_month = (next_month - date(today.year, today.month, 1)).days
    return min(today.day / max(days_in_month, 1), 1.0)


def _projected_month_spend(spent: float) -> float:
    progress = max(_month_progress(), 0.01)
    return spent / progress


def _append_expense_from_recurring(rule: dict) -> None:
    expenses = _rows("expense_records")
    expense = {
        "expense_id": f"EXP-{uuid4().hex[:8].upper()}",
        "expense_date": date.today().isoformat(),
        "category": str(rule.get("category", "Otro")),
        "amount": _num(rule.get("amount")),
        "gross_amount": _num(rule.get("amount")),
        "business_percent": 100.0,
        "payment_method": str(rule.get("payment_method", "Otro")),
        "responsible": str(rule.get("responsible", "Sin asignar")),
        "description": f"Recurrente: {rule.get('name', 'Gasto recurrente')}",
        "supplier": str(rule.get("supplier", "")),
        "reference": str(rule.get("recurring_id", "")),
        "status": "Registrado",
        "source_recurring_id": str(rule.get("recurring_id", "")),
        "created_at_utc": _now(),
    }
    expenses.append(expense)
    _save("expense_records", expenses)
    if rule.get("register_cash", True):
        base._append_cash_expense(expense)


def _export_commitments(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Periodo", "Categoría", "Proveedor", "Monto", "Estado", "Vence", "Responsable", "Descripción"])
    for row in rows:
        writer.writerow([
            row.get("commitment_id", ""), row.get("period", ""), row.get("category", ""), row.get("supplier", ""),
            row.get("amount", 0), row.get("status", ""), row.get("due_date", ""), row.get("responsible", ""), row.get("description", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def _supplier_totals(expenses: list[dict]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "amount": 0.0})
    for row in expenses:
        supplier = str(row.get("supplier", "Sin proveedor")) or "Sin proveedor"
        output[supplier]["count"] += 1
        output[supplier]["amount"] += _num(row.get("amount"))
    return output


def render_expenses_budget_control() -> None:
    render_page_header(
        "Gastos y presupuesto",
        "Agrega recurrentes, compromisos, forecast mensual, proveedores críticos y plan de ahorro.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_expenses_budget_plus()
    finally:
        base.render_page_header = original_header

    expenses = _rows("expense_records")
    budgets = _rows("budget_lines")
    recurring = _rows("expense_recurring_rules")
    commitments = _rows("expense_commitments")
    forecasts = _rows("budget_forecasts")
    savings = _rows("budget_savings_actions")
    period = _month_key()
    current_expenses = _period_expenses(expenses, period)
    spent_by_category = _spent_by_category(current_expenses)
    open_commitments = [row for row in commitments if row.get("status") in {"Pendiente", "Comprometido"} and row.get("period") == period]
    committed_total = sum(_num(row.get("amount")) for row in open_commitments)
    spent_total = sum(_num(row.get("amount")) for row in current_expenses)
    budget_total = sum(_num(row.get("amount")) for row in budgets if row.get("period") == period and row.get("status", "Activo") == "Activo")
    projected = _projected_month_spend(spent_total)
    projected_gap = budget_total - projected - committed_total
    overdue_commitments = [row for row in open_commitments if str(row.get("due_date", "")) < date.today().isoformat()]

    st.divider()
    st.markdown("### Control avanzado de presupuesto")
    metrics = st.columns(5)
    metrics[0].metric("Proyección mensual", format_money(projected, get_currency()))
    metrics[1].metric("Comprometido", format_money(committed_total, get_currency()))
    metrics[2].metric("Brecha proyectada", format_money(projected_gap, get_currency()))
    metrics[3].metric("Recurrentes", str(len([row for row in recurring if row.get("status", "Activo") == "Activo"])))
    metrics[4].metric("Compromisos vencidos", str(len(overdue_commitments)))

    if projected_gap < 0:
        st.error("La proyección del mes más compromisos supera el presupuesto disponible.")
    elif budget_total and projected_gap < budget_total * 0.1:
        st.warning("La brecha proyectada es menor al 10% del presupuesto. Conviene revisar gastos discrecionales.")
    if overdue_commitments:
        st.warning("Hay compromisos de gasto vencidos sin cerrar.")

    recurring_tab, commitments_tab, forecast_tab, suppliers_tab, savings_tab = st.tabs(("Recurrentes", "Compromisos", "Forecast", "Proveedores", "Ahorro"))

    with recurring_tab:
        with st.form("expense_recurring_rule_form", clear_on_submit=True):
            cols = st.columns(5)
            name = cols[0].text_input("Nombre", placeholder="Internet, Adobe, luz")
            category = cols[1].selectbox("Categoría", base.CATEGORIES)
            amount = cols[2].number_input("Monto", min_value=0.01, value=1.0, step=1.0)
            day = cols[3].number_input("Día sugerido", min_value=1, max_value=31, value=min(date.today().day, 28), step=1)
            payment_method = cols[4].selectbox("Método", base.PAYMENT_METHODS)
            extra = st.columns(3)
            supplier = extra[0].text_input("Proveedor")
            responsible = extra[1].text_input("Responsable")
            register_cash = extra[2].checkbox("Crear egreso en caja al generar", value=True)
            submitted = st.form_submit_button("Guardar recurrente", type="primary", use_container_width=True)
        if submitted:
            if not name.strip() or not responsible.strip():
                st.error("Nombre y responsable son obligatorios.")
            else:
                recurring.append({
                    "recurring_id": f"REC-{uuid4().hex[:8].upper()}",
                    "name": name.strip(),
                    "category": category,
                    "amount": float(amount),
                    "day": int(day),
                    "payment_method": payment_method,
                    "supplier": supplier.strip(),
                    "responsible": responsible.strip(),
                    "register_cash": bool(register_cash),
                    "status": "Activo",
                    "created_at_utc": _now(),
                })
                _save("expense_recurring_rules", recurring)
                st.rerun()
        for rule in reversed(recurring[-100:]):
            generated_this_month = any(str(row.get("source_recurring_id", "")) == str(rule.get("recurring_id", "")) and str(row.get("expense_date", ""))[:7] == period for row in expenses)
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{rule.get('name', 'Recurrente')}**")
                cols[0].caption(f"{rule.get('category', '')} · día {rule.get('day', '')} · {rule.get('supplier', '')}")
                cols[1].metric("Monto", format_money(_num(rule.get("amount")), get_currency()))
                cols[2].metric("Estado", str(rule.get("status", "Activo")))
                if cols[3].button("Generar gasto", key=f"generate_recurring_{rule.get('recurring_id')}", use_container_width=True, disabled=generated_this_month or rule.get("status") != "Activo"):
                    _append_expense_from_recurring(rule)
                    st.rerun()

    with commitments_tab:
        with st.form("expense_commitment_form", clear_on_submit=True):
            cols = st.columns(5)
            commitment_period = cols[0].text_input("Periodo", value=period)
            category = cols[1].selectbox("Categoría", base.CATEGORIES, key="commitment_category")
            amount = cols[2].number_input("Monto comprometido", min_value=0.01, value=1.0, step=1.0)
            due_date = cols[3].date_input("Fecha límite", value=date.today() + timedelta(days=7))
            responsible = cols[4].text_input("Responsable")
            supplier = st.text_input("Proveedor")
            description = st.text_area("Descripción", max_chars=500)
            submitted = st.form_submit_button("Crear compromiso", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip() or not description.strip():
                st.error("Responsable y descripción son obligatorios.")
            else:
                commitments.append({
                    "commitment_id": f"COM-{uuid4().hex[:8].upper()}",
                    "period": commitment_period.strip() or period,
                    "category": category,
                    "amount": float(amount),
                    "due_date": due_date.isoformat(),
                    "supplier": supplier.strip(),
                    "responsible": responsible.strip(),
                    "description": description.strip(),
                    "status": "Comprometido",
                    "created_at_utc": _now(),
                })
                _save("expense_commitments", commitments)
                st.rerun()
        st.download_button("Descargar compromisos CSV", data=_export_commitments(commitments), file_name=f"compromisos_gasto_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not commitments)
        for row in reversed(commitments[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row.get('commitment_id', '')} · {row.get('description', '')}**")
                cols[0].caption(f"{row.get('period', '')} · {row.get('category', '')} · {row.get('supplier', '')}")
                cols[1].metric("Monto", format_money(_num(row.get("amount")), get_currency()))
                cols[2].metric("Vence", str(row.get("due_date", "")))
                if cols[3].button("Cerrar", key=f"close_commitment_{row.get('commitment_id')}", use_container_width=True, disabled=row.get("status") == "Cerrado"):
                    changed = []
                    for item in commitments:
                        current = dict(item)
                        if current.get("commitment_id") == row.get("commitment_id"):
                            current["status"] = "Cerrado"
                            current["closed_at_utc"] = _now()
                        changed.append(current)
                    _save("expense_commitments", changed)
                    st.rerun()

    with forecast_tab:
        st.markdown("#### Pronóstico del mes")
        forecast_rows = []
        for category in base.CATEGORIES:
            spent = spent_by_category.get(category, 0.0)
            projected_category = _projected_month_spend(spent)
            budget = _budget_for(category, period, budgets)
            amount = _num(budget.get("amount")) if budget else 0.0
            committed = sum(_num(row.get("amount")) for row in open_commitments if row.get("category") == category)
            if spent or amount or committed:
                forecast_rows.append((category, spent, projected_category, committed, amount, amount - projected_category - committed))
        for category, spent, projected_category, committed, amount, gap in forecast_rows:
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1, 1])
                cols[0].markdown(f"**{category}**")
                cols[1].metric("Gastado", format_money(spent, get_currency()))
                cols[2].metric("Proyectado", format_money(projected_category, get_currency()))
                cols[3].metric("Comprometido", format_money(committed, get_currency()))
                cols[4].metric("Brecha", format_money(gap, get_currency()))
                if gap < 0:
                    st.error("Proyección superior al presupuesto disponible.")
        if st.button("Guardar forecast del mes", type="primary", use_container_width=True):
            forecasts.append({
                "forecast_id": f"FCB-{uuid4().hex[:8].upper()}",
                "period": period,
                "spent": spent_total,
                "budget": budget_total,
                "committed": committed_total,
                "projected": projected,
                "projected_gap": projected_gap,
                "created_at_utc": _now(),
            })
            _save("budget_forecasts", forecasts)
            st.rerun()
        for row in reversed(forecasts[-20:]):
            st.write(f"**{row.get('forecast_id', '')} · {row.get('period', '')}** · proyectado {format_money(_num(row.get('projected')), get_currency())} · brecha {format_money(_num(row.get('projected_gap')), get_currency())}")

    with suppliers_tab:
        totals = _supplier_totals(current_expenses)
        if not totals:
            st.info("No hay gastos con proveedor en el periodo actual.")
        for supplier, data in sorted(totals.items(), key=lambda item: item[1]["amount"], reverse=True)[:50]:
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{supplier}**")
                cols[1].metric("Gastos", str(int(data["count"])))
                cols[2].metric("Total", format_money(data["amount"], get_currency()))
        if st.button("Guardar resumen por proveedor", use_container_width=True, disabled=not totals):
            summaries = _rows("expense_supplier_summary")
            summaries.append({
                "summary_id": f"SUP-{uuid4().hex[:8].upper()}",
                "period": period,
                "rows": [{"supplier": supplier, **data} for supplier, data in totals.items()],
                "created_at_utc": _now(),
            })
            _save("expense_supplier_summary", summaries)
            st.rerun()

    with savings_tab:
        with st.form("budget_savings_action_form", clear_on_submit=True):
            cols = st.columns(4)
            category = cols[0].selectbox("Categoría", base.CATEGORIES, key="saving_category")
            target_amount = cols[1].number_input("Ahorro objetivo", min_value=0.01, value=1.0, step=1.0)
            responsible = cols[2].text_input("Responsable")
            due_date = cols[3].date_input("Fecha compromiso", value=date.today() + timedelta(days=7))
            action = st.text_area("Acción de ahorro", max_chars=500)
            submitted = st.form_submit_button("Crear acción de ahorro", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip() or not action.strip():
                st.error("Responsable y acción son obligatorios.")
            else:
                savings.append({
                    "saving_id": f"SAV-{uuid4().hex[:8].upper()}",
                    "period": period,
                    "category": category,
                    "target_amount": float(target_amount),
                    "responsible": responsible.strip(),
                    "due_date": due_date.isoformat(),
                    "action": action.strip(),
                    "status": "Abierta",
                    "created_at_utc": _now(),
                })
                _save("budget_savings_actions", savings)
                st.rerun()
        if not savings:
            st.info("No hay acciones de ahorro registradas.")
        for row in reversed(savings[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{row.get('saving_id', '')} · {row.get('category', '')}**")
                cols[0].caption(f"{row.get('responsible', '')} · compromiso {row.get('due_date', '')} · {row.get('action', '')}")
                cols[1].metric("Meta", format_money(_num(row.get("target_amount")), get_currency()))
                if cols[2].button("Completar", key=f"complete_saving_{row.get('saving_id')}", use_container_width=True, disabled=row.get("status") == "Completada"):
                    changed = []
                    for item in savings:
                        current = dict(item)
                        if current.get("saving_id") == row.get("saving_id"):
                            current["status"] = "Completada"
                            current["completed_at_utc"] = _now()
                        changed.append(current)
                    _save("budget_savings_actions", changed)
                    st.rerun()

    render_info_card(
        "Presupuesto preventivo",
        "Además de registrar gastos, ahora puedes anticipar compromisos, recurrentes, proveedores fuertes y acciones de ahorro.",
        "CONTROL PRESUPUESTARIO",
    )


app_shell.FUNCTIONAL_MODULES["Gastos y presupuesto"] = render_expenses_budget_control
