"""Gastos y presupuesto mensual para CopyMary ERP."""

from datetime import date
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _records

CATEGORIES = ("Internet", "Electricidad", "Transporte", "Software", "Mantenimiento", "Publicidad", "Materiales", "Servicios", "Retiros", "Otro")
METHODS = ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro")


def _month(raw: str) -> str:
    return raw[:7] if len(raw) >= 7 else ""


def _budget(category: str, month: str, budgets: list[dict]) -> float:
    for item in budgets:
        if item.get("category") == category and item.get("month") == month:
            return float(item.get("amount", 0.0))
    return 0.0


def render_expenses_budget() -> None:
    with st.container(border=True):
        render_page_header("Gastos y presupuesto", "Registra gastos y controla límites mensuales por categoría.")
        st.caption("Cada gasto genera un egreso en Caja.")

    expenses = _records("expense_records")
    budgets = _records("expense_budgets")
    recurring = _records("recurring_expenses")
    cash = _records("cash_movements")
    current_month = date.today().strftime("%Y-%m")
    month_expenses = [item for item in expenses if _month(str(item.get("expense_date", ""))) == current_month]
    spent = sum(float(item.get("amount", 0.0)) for item in month_expenses)
    limit_total = sum(float(item.get("amount", 0.0)) for item in budgets if item.get("month") == current_month)

    metrics = st.columns(4)
    metrics[0].metric("Gastos del mes", format_money(spent))
    metrics[1].metric("Presupuesto", format_money(limit_total))
    metrics[2].metric("Disponible", format_money(limit_total - spent))
    metrics[3].metric("Recurrentes", str(len(recurring)))

    tab1, tab2, tab3, tab4 = st.tabs(("Registrar", "Presupuesto", "Recurrentes", "Historial"))

    with tab1:
        with st.form("expense_form", clear_on_submit=True):
            cols = st.columns(4)
            expense_date = cols[0].date_input("Fecha", value=date.today())
            category = cols[1].selectbox("Categoría", CATEGORIES)
            amount = cols[2].number_input("Monto", min_value=0.01, value=1.0, step=0.5)
            method = cols[3].selectbox("Método", METHODS)
            description = st.text_input("Descripción", max_chars=180)
            submitted = st.form_submit_button("Registrar gasto", type="primary", use_container_width=True)
        if submitted and description.strip():
            expense_id = uuid4().hex[:10]
            created = _now()
            expenses.append({"expense_id": expense_id, "created_at_utc": created, "expense_date": expense_date.isoformat(), "category": category, "amount": float(amount), "payment_method": method, "description": description.strip(), "source": "Manual"})
            cash.append({"movement_id": uuid4().hex[:10], "created_at_utc": created, "movement_type": "Egreso", "category": category, "amount": float(amount), "payment_method": method, "reference": expense_id, "notes": description.strip()})
            st.session_state["expense_records"] = expenses
            st.session_state["cash_movements"] = cash
            st.rerun()

    with tab2:
        month = st.text_input("Mes", value=current_month, help="Formato AAAA-MM")
        with st.form("budget_form"):
            category = st.selectbox("Categoría", CATEGORIES, key="budget_category")
            amount = st.number_input("Límite mensual", min_value=0.0, value=_budget(category, month, budgets), step=1.0)
            save_budget = st.form_submit_button("Guardar presupuesto", type="primary", use_container_width=True)
        if save_budget:
            updated = []
            found = False
            for item in budgets:
                current = dict(item)
                if item.get("category") == category and item.get("month") == month:
                    current["amount"] = float(amount)
                    found = True
                updated.append(current)
            if not found:
                updated.append({"budget_id": uuid4().hex[:10], "category": category, "month": month, "amount": float(amount)})
            st.session_state["expense_budgets"] = updated
            st.rerun()

        for category_name in CATEGORIES:
            category_limit = _budget(category_name, month, budgets)
            category_spent = sum(float(item.get("amount", 0.0)) for item in expenses if item.get("category") == category_name and _month(str(item.get("expense_date", ""))) == month)
            if category_limit <= 0 and category_spent <= 0:
                continue
            with st.container(border=True):
                row = st.columns(4)
                row[0].metric("Categoría", category_name)
                row[1].metric("Límite", format_money(category_limit))
                row[2].metric("Gastado", format_money(category_spent))
                row[3].metric("Disponible", format_money(category_limit - category_spent))
                if category_limit > 0:
                    st.progress(min(category_spent / category_limit, 1.0))
                if category_limit > 0 and category_spent > category_limit:
                    st.error("Presupuesto excedido.")

    with tab3:
        with st.form("recurring_form", clear_on_submit=True):
            cols = st.columns(3)
            name = cols[0].text_input("Nombre", max_chars=100)
            category = cols[1].selectbox("Categoría", CATEGORIES, key="recurring_category")
            amount = cols[2].number_input("Monto", min_value=0.01, value=1.0, step=0.5, key="recurring_amount")
            submitted = st.form_submit_button("Crear recurrente", type="primary", use_container_width=True)
        if submitted and name.strip():
            recurring.append({"recurring_id": uuid4().hex[:10], "name": name.strip(), "category": category, "amount": float(amount), "last_applied_month": ""})
            st.session_state["recurring_expenses"] = recurring
            st.rerun()

        for item in recurring:
            with st.container(border=True):
                cols = st.columns(4)
                cols[0].metric("Gasto", str(item.get("name", "")))
                cols[1].metric("Monto", format_money(float(item.get("amount", 0.0))))
                cols[2].metric("Último mes", str(item.get("last_applied_month") or "Nunca"))
                applied = item.get("last_applied_month") == current_month
                if cols[3].button("Aplicado" if applied else "Aplicar", key=f"apply_{item.get('recurring_id')}", disabled=applied, use_container_width=True):
                    expense_id = uuid4().hex[:10]
                    created = _now()
                    expenses.append({"expense_id": expense_id, "created_at_utc": created, "expense_date": date.today().isoformat(), "category": item.get("category", "Otro"), "amount": float(item.get("amount", 0.0)), "payment_method": "Otro", "description": item.get("name", "Gasto recurrente"), "source": "Recurrente"})
                    cash.append({"movement_id": uuid4().hex[:10], "created_at_utc": created, "movement_type": "Egreso", "category": item.get("category", "Otro"), "amount": float(item.get("amount", 0.0)), "payment_method": "Otro", "reference": expense_id, "notes": item.get("name", "Gasto recurrente")})
                    for current in recurring:
                        if current.get("recurring_id") == item.get("recurring_id"):
                            current["last_applied_month"] = current_month
                    st.session_state["expense_records"] = expenses
                    st.session_state["cash_movements"] = cash
                    st.session_state["recurring_expenses"] = recurring
                    st.rerun()

    with tab4:
        for item in sorted(expenses, key=lambda value: str(value.get("expense_date", "")), reverse=True):
            with st.container(border=True):
                cols = st.columns([3, 1])
                cols[0].markdown(f"### {item.get('description', 'Gasto')}")
                cols[0].caption(f"{item.get('expense_date', '')} · {item.get('category', '')} · {item.get('source', 'Manual')}")
                cols[1].metric("Monto", format_money(float(item.get("amount", 0.0))))

    render_info_card("Control presupuestario", "Los límites generan alertas, pero no bloquean el registro de gastos.", "GESTIÓN TEMPORAL")
