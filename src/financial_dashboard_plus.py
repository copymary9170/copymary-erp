"""Resumen ejecutivo y alertas para Panel financiero y cierres."""

from collections import defaultdict
from datetime import date, datetime

import streamlit as st

from src import financial_control as base
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import read_list as _rows


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _record_month(record: dict) -> str:
    raw = str(record.get("created_at_utc", record.get("created_at", record.get("date", ""))))
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return raw[:7] if len(raw) >= 7 else ""


def _shift_month(month: str, offset: int) -> str:
    year, number = (int(part) for part in month.split("-"))
    absolute = year * 12 + number - 1 + offset
    return f"{absolute // 12}-{absolute % 12 + 1:02d}"


def _sale_paid(sale: dict, payments: list[dict]) -> float:
    sale_id = str(sale.get("sale_id", ""))
    explicit = sum(
        _number(item.get("amount"))
        for item in payments
        if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
    )
    total = _number(sale.get("total"))
    if explicit > 0:
        return min(explicit, total)
    return total if sale.get("payment_status") == "Pagado" else 0.0


def _purchase_paid(purchase: dict, payments: list[dict]) -> float:
    purchase_id = str(purchase.get("purchase_id", ""))
    explicit = sum(
        _number(item.get("amount"))
        for item in payments
        if str(item.get("purchase_id", "")) == purchase_id and not item.get("reversed")
    )
    total = _number(purchase.get("total"))
    if explicit > 0:
        return min(explicit, total)
    return total if purchase.get("payment_status") == "Pagado" else 0.0


def _go(area: str, page: str) -> None:
    st.session_state["pending_navigation_area"] = area
    st.session_state["pending_navigation_page"] = page
    st.rerun()


def _button(label: str, area: str, page: str, key: str, primary: bool = False) -> None:
    if st.button(label, key=key, use_container_width=True, type="primary" if primary else "secondary"):
        _go(area, page)


def _monthly_trend(month: str) -> list[dict]:
    cash = _rows("cash_movements")
    sales = _rows("sales_registry")
    rows: list[dict] = []
    for offset in range(-5, 1):
        current = _shift_month(month, offset)
        current_cash = [item for item in cash if _record_month(item) == current]
        current_sales = [
            item for item in sales
            if _record_month(item) == current
            and item.get("order_status") not in {"Cancelado", "Cancelada", "Anulado", "Anulada"}
        ]
        income = sum(_number(item.get("amount")) for item in current_cash if item.get("movement_type") == "Ingreso")
        expenses = sum(_number(item.get("amount")) for item in current_cash if item.get("movement_type") == "Egreso")
        profit = sum(_number(item.get("total")) - _number(item.get("estimated_cost")) for item in current_sales)
        rows.append({"Mes": current, "Ingresos": income, "Egresos": expenses, "Saldo": income - expenses, "Utilidad estimada": profit})
    return rows


def render_financial_dashboard_plus() -> None:
    render_page_header(
        "Panel financiero y cierres",
        "Liquidez, obligaciones, rentabilidad, cierres y alertas reunidos para controlar el dinero del negocio.",
    )

    cash = _rows("cash_movements")
    sales = [
        item for item in _rows("sales_registry")
        if item.get("order_status") not in {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    ]
    purchases = [
        item for item in _rows("purchases_registry")
        if item.get("receipt_status") not in {"Cancelada", "Cancelado", "Anulada", "Anulado"}
    ]
    customer_payments = _rows("payment_records")
    supplier_payments = _rows("supplier_payment_records")
    closings = _rows("cash_closings")

    month = date.today().strftime("%Y-%m")
    month_cash = [item for item in cash if _record_month(item) == month]
    month_sales = [item for item in sales if _record_month(item) == month]
    month_purchases = [item for item in purchases if _record_month(item) == month]

    income = sum(_number(item.get("amount")) for item in month_cash if item.get("movement_type") == "Ingreso")
    expenses = sum(_number(item.get("amount")) for item in month_cash if item.get("movement_type") == "Egreso")
    cash_balance = income - expenses
    billed = sum(_number(item.get("total")) for item in month_sales)
    estimated_profit = sum(_number(item.get("total")) - _number(item.get("estimated_cost")) for item in month_sales)
    purchases_total = sum(_number(item.get("total")) for item in month_purchases)
    receivables = sum(max(_number(item.get("total")) - _sale_paid(item, customer_payments), 0.0) for item in sales)
    payables = sum(max(_number(item.get("total")) - _purchase_paid(item, supplier_payments), 0.0) for item in purchases)
    working_position = cash_balance + receivables - payables
    margin = estimated_profit / billed * 100 if billed else 0.0
    expense_ratio = expenses / income * 100 if income else 0.0

    first = st.columns(4)
    first[0].metric("Saldo de caja del mes", format_money(cash_balance))
    first[1].metric("Por cobrar total", format_money(receivables))
    first[2].metric("Por pagar total", format_money(payables))
    first[3].metric("Posición financiera", format_money(working_position))

    second = st.columns(4)
    second[0].metric("Ventas facturadas", format_money(billed))
    second[1].metric("Utilidad estimada", format_money(estimated_profit))
    second[2].metric("Margen estimado", f"{margin:,.1f}%")
    second[3].metric("Gastos sobre ingresos", f"{expense_ratio:,.1f}%")

    if cash_balance < 0:
        st.error("El saldo de caja del mes es negativo. Revisa egresos, cobros pendientes y pagos próximos.")
    elif payables > cash_balance + receivables:
        st.warning("Las obligaciones superan la caja disponible más las cuentas por cobrar.")
    elif receivables > income:
        st.warning("Las cuentas por cobrar superan los ingresos registrados del mes; conviene acelerar la cobranza.")
    else:
        st.success("La posición financiera no presenta una alerta crítica inmediata.")

    st.markdown("### Acciones financieras")
    action_columns = st.columns(4)
    with action_columns[0]:
        render_info_card("Cobranza", f"Pendiente: {format_money(receivables)}.", "LIQUIDEZ")
        _button("Abrir cuentas por cobrar", "Ventas y clientes", "Cuentas por cobrar", "finance_receivables", bool(receivables))
    with action_columns[1]:
        render_info_card("Proveedores", f"Pendiente: {format_money(payables)}.", "OBLIGACIONES")
        _button("Abrir cuentas por pagar", "Compras y proveedores", "Cuentas por pagar", "finance_payables", bool(payables))
    with action_columns[2]:
        render_info_card("Gastos", f"Egresos del mes: {format_money(expenses)}.", "CONTROL")
        _button("Abrir gastos", "Administración", "Gastos y presupuesto", "finance_expenses")
    with action_columns[3]:
        render_info_card("Conciliación", "Comprueba pagos, reversos y movimientos antes del cierre.", "SEGURIDAD")
        _button("Abrir conciliación", "Administración", "Conciliación financiera", "finance_reconciliation")

    st.markdown("### Tendencia de seis meses")
    trend = _monthly_trend(month)
    st.dataframe(trend, use_container_width=True, hide_index=True)
    latest = trend[-1]
    previous = trend[-2]
    trend_metrics = st.columns(3)
    trend_metrics[0].metric("Cambio de ingresos", format_money(latest["Ingresos"] - previous["Ingresos"]))
    trend_metrics[1].metric("Cambio de egresos", format_money(latest["Egresos"] - previous["Egresos"]))
    trend_metrics[2].metric("Cambio de saldo", format_money(latest["Saldo"] - previous["Saldo"]))

    st.markdown("### Distribución por método de pago")
    method_totals: dict[str, float] = defaultdict(float)
    for item in month_cash:
        sign = 1 if item.get("movement_type") == "Ingreso" else -1
        method = str(item.get("payment_method", "Otro")) or "Otro"
        method_totals[method] += sign * _number(item.get("amount"))
    if method_totals:
        method_columns = st.columns(min(len(method_totals), 5))
        for index, (method, total) in enumerate(sorted(method_totals.items(), key=lambda item: item[1], reverse=True)):
            method_columns[index % len(method_columns)].metric(method, format_money(total))
    else:
        st.info("No hay movimientos del mes para analizar por método de pago.")

    st.markdown("### Salud de los cierres")
    closing_differences = [_number(item.get("difference")) for item in closings]
    closings_with_difference = sum(1 for value in closing_differences if abs(value) > 0.01)
    last_closing = closings[-1] if closings else None
    closing_metrics = st.columns(4)
    closing_metrics[0].metric("Cierres registrados", str(len(closings)))
    closing_metrics[1].metric("Con diferencia", str(closings_with_difference))
    closing_metrics[2].metric("Diferencia acumulada", format_money(sum(closing_differences)))
    closing_metrics[3].metric("Último cierre", str(last_closing.get("closing_date", "Sin cierres")) if last_closing else "Sin cierres")

    if closings_with_difference:
        st.error(f"Hay {closings_with_difference} cierre(s) con diferencias que deben investigarse.")
    elif closings:
        st.success("Los cierres registrados no presentan diferencias acumuladas relevantes.")
    else:
        st.info("Todavía no hay cierres registrados.")

    st.markdown("### Recomendaciones automáticas")
    recommendations: list[str] = []
    if receivables > 0:
        recommendations.append("Prioriza los cobros de mayor saldo para reforzar la liquidez antes de asumir nuevas obligaciones.")
    if expense_ratio > 80:
        recommendations.append("Los egresos representan más del 80% de los ingresos del mes; revisa gastos no esenciales.")
    if margin and margin < 30:
        recommendations.append("El margen estimado está por debajo de 30%; revisa costos, descuentos y precios de venta.")
    if purchases_total > billed:
        recommendations.append("Las compras del mes superan las ventas facturadas; revisa rotación de inventario y planificación de compras.")
    if closings_with_difference:
        recommendations.append("Corrige las diferencias históricas de cierre antes de confiar en el saldo acumulado.")
    if not recommendations:
        recommendations.append("Mantén el seguimiento de caja, cobranza y cierres con la frecuencia actual.")
    for recommendation in recommendations:
        st.info(recommendation)

    st.divider()
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_financial_control()
    finally:
        base.render_page_header = original_header

    render_info_card(
        "Control financiero integral",
        "El resumen ejecutivo se complementa con el cierre seguro, la conciliación y el historial detallado existentes.",
        "FINANZAS Y CIERRES",
    )
