"""Panel financiero y cierres temporales de caja para CopyMary ERP."""

import csv
from datetime import date, datetime
from io import StringIO
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _records, save_list as _save


def _date_from_utc(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _filter_by_period(items: list[dict], start: date, end: date) -> list[dict]:
    filtered: list[dict] = []
    for item in items:
        item_date = _date_from_utc(str(item.get("created_at_utc", "")))
        if item_date is not None and start <= item_date <= end:
            filtered.append(item)
    return filtered


def _cash_totals(movements: list[dict]) -> tuple[float, float, float]:
    income = sum(float(item.get("amount", 0.0)) for item in movements if item.get("movement_type") == "Ingreso")
    expenses = sum(float(item.get("amount", 0.0)) for item in movements if item.get("movement_type") == "Egreso")
    return income, expenses, income - expenses


def _sales_totals(sales: list[dict]) -> tuple[float, float, float]:
    valid = [sale for sale in sales if sale.get("order_status") != "Cancelado"]
    billed = sum(float(sale.get("total", 0.0)) for sale in valid)
    costs = sum(float(sale.get("estimated_cost", 0.0)) for sale in valid)
    return billed, costs, billed - costs


def _build_financial_csv(
    cash: list[dict],
    sales: list[dict],
    purchases: list[dict],
    start: date,
    end: date,
) -> bytes:
    currency = get_currency()
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(["Reporte financiero CopyMary ERP"])
    writer.writerow(["Desde", start.isoformat(), "Hasta", end.isoformat(), "Moneda", currency])
    writer.writerow([])
    writer.writerow(["CAJA"])
    writer.writerow(["Fecha UTC", "Tipo", "Categoría", "Monto", "Método", "Referencia", "Notas"])
    for item in cash:
        writer.writerow([
            item.get("created_at_utc", ""),
            item.get("movement_type", ""),
            item.get("category", ""),
            f"{float(item.get('amount', 0.0)):.4f}",
            item.get("payment_method", ""),
            item.get("reference", ""),
            item.get("notes", ""),
        ])
    writer.writerow([])
    writer.writerow(["VENTAS"])
    writer.writerow(["Fecha UTC", "ID", "Descripción", "Total", "Costo estimado", "Ganancia estimada", "Pago", "Estado"])
    for sale in sales:
        total = float(sale.get("total", 0.0))
        cost = float(sale.get("estimated_cost", 0.0))
        writer.writerow([
            sale.get("created_at_utc", ""),
            sale.get("sale_id", ""),
            sale.get("description", ""),
            f"{total:.4f}",
            f"{cost:.4f}",
            f"{total - cost:.4f}",
            sale.get("payment_status", ""),
            sale.get("order_status", ""),
        ])
    writer.writerow([])
    writer.writerow(["COMPRAS"])
    writer.writerow(["Fecha UTC", "ID", "Material", "Total", "Pago", "Recepción"])
    for purchase in purchases:
        writer.writerow([
            purchase.get("created_at_utc", ""),
            purchase.get("purchase_id", ""),
            purchase.get("material_name", ""),
            f"{float(purchase.get('total', 0.0)):.4f}",
            purchase.get("payment_status", ""),
            purchase.get("receipt_status", ""),
        ])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def render_financial_dashboard() -> None:
    with st.container(border=True):
        render_page_header(
            "Panel financiero y cierres",
            "Analiza ingresos, egresos, ventas, compras y registra cierres de caja.",
        )
        st.caption("Los resultados dependen de los datos registrados durante la sesión.")

    cash = _records("cash_movements")
    sales = _records("sales_registry")
    purchases = _records("purchases_registry")
    closings = _records("cash_closings")

    today = date.today()
    period_columns = st.columns(2)
    with period_columns[0]:
        start_date = st.date_input("Desde", value=today.replace(day=1), key="financial_start")
    with period_columns[1]:
        end_date = st.date_input("Hasta", value=today, key="financial_end")

    if start_date > end_date:
        st.error("La fecha inicial no puede ser posterior a la fecha final.")
        return

    period_cash = _filter_by_period(cash, start_date, end_date)
    period_sales = _filter_by_period(sales, start_date, end_date)
    period_purchases = _filter_by_period(purchases, start_date, end_date)

    income, expenses, cash_balance = _cash_totals(period_cash)
    billed, estimated_costs, estimated_profit = _sales_totals(period_sales)
    purchase_total = sum(
        float(item.get("total", 0.0))
        for item in period_purchases
        if item.get("receipt_status") != "Cancelada"
    )

    first = st.columns(4)
    first[0].metric("Ingresos", format_money(income))
    first[1].metric("Egresos", format_money(expenses))
    first[2].metric("Saldo de caja", format_money(cash_balance))
    first[3].metric("Compras registradas", format_money(purchase_total))

    second = st.columns(3)
    second[0].metric("Ventas facturadas", format_money(billed))
    second[1].metric("Costos estimados", format_money(estimated_costs))
    second[2].metric("Utilidad estimada", format_money(estimated_profit))

    st.download_button(
        "Descargar reporte financiero CSV",
        data=_build_financial_csv(period_cash, period_sales, period_purchases, start_date, end_date),
        file_name=f"copymary_finanzas_{start_date}_{end_date}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()
    st.subheader("Resumen por categoría")
    categories: dict[str, float] = {}
    for movement in period_cash:
        category = str(movement.get("category", "Otro"))
        sign = 1 if movement.get("movement_type") == "Ingreso" else -1
        categories[category] = categories.get(category, 0.0) + sign * float(movement.get("amount", 0.0))

    if not categories:
        st.info("No hay movimientos para resumir en el período seleccionado.")
    else:
        for category, amount in sorted(categories.items(), key=lambda item: abs(item[1]), reverse=True):
            st.metric(category, format_money(amount))

    st.divider()
    st.subheader("Registrar cierre de caja")
    total_session_income, total_session_expenses, expected_balance = _cash_totals(cash)

    with st.form("cash_closing_form", clear_on_submit=True):
        row = st.columns(4)
        with row[0]:
            closing_date = st.date_input("Fecha del cierre", value=today)
        with row[1]:
            counted_cash = st.number_input("Dinero contado", min_value=0.0, value=max(expected_balance, 0.0), step=1.0)
        with row[2]:
            responsible = st.text_input("Responsable", max_chars=80)
        with row[3]:
            method_scope = st.selectbox("Alcance", ("Todos los métodos", "Solo efectivo"))
        notes = st.text_area("Observaciones", max_chars=300)
        submitted = st.form_submit_button("Guardar cierre", type="primary", use_container_width=True)

    if submitted:
        difference = float(counted_cash) - expected_balance
        closings.append(
            {
                "closing_id": uuid4().hex[:10],
                "created_at_utc": _now(),
                "closing_date": closing_date.isoformat(),
                "expected_balance": expected_balance,
                "counted_cash": float(counted_cash),
                "difference": difference,
                "responsible": responsible.strip(),
                "method_scope": method_scope,
                "notes": notes.strip(),
                "income_total": total_session_income,
                "expense_total": total_session_expenses,
            }
        )
        _save("cash_closings", closings)
        st.success("Cierre de caja guardado.")
        st.rerun()

    st.subheader("Historial de cierres")
    if not closings:
        st.info("Todavía no hay cierres registrados.")
    else:
        for closing in reversed(closings):
            with st.container(border=True):
                st.markdown(f"### Cierre {closing.get('closing_date', '')}")
                st.caption(
                    f"ID {closing.get('closing_id', '')} · Responsable: {closing.get('responsible') or 'No indicado'}"
                )
                columns = st.columns(4)
                columns[0].metric("Esperado", format_money(float(closing.get("expected_balance", 0.0))))
                columns[1].metric("Contado", format_money(float(closing.get("counted_cash", 0.0))))
                columns[2].metric("Diferencia", format_money(float(closing.get("difference", 0.0))))
                columns[3].metric("Alcance", str(closing.get("method_scope", "")))
                render_info_card(
                    "Observaciones",
                    str(closing.get("notes") or "Sin observaciones"),
                    "CIERRE TEMPORAL",
                )

    render_info_card(
        "Lectura financiera",
        "El saldo de caja refleja movimientos reales registrados; la utilidad es estimada según los costos cargados en cada venta.",
        "CONTROL ADMINISTRATIVO",
    )
