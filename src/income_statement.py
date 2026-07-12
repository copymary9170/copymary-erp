"""Estado de Resultados (P&L) para CopyMary ERP.

Gap real detectado en la revisión de negocio (dueña + finanzas + producción):
existen costeo, ventas, gastos, y ahora nómina, pero ningún reporte que
consolide "cuánto ganó el negocio" por período. `financial_dashboard_plus.py`
calcula una "utilidad estimada" (ventas - costo estimado), pero no resta
gastos operativos ni nómina, así que no es un estado de resultados real.

Alcance: ingresos - costo de ventas = utilidad bruta; utilidad bruta - gastos
operativos - nómina = utilidad neta. Base caja/devengo simplificada
(ingresos = ventas facturadas del mes sin cancelar, no filtra por cobradas —
para eso está "Cuentas por cobrar"; ver PANEL FINANCIERO para liquidez real).

No es un estado de resultados contable/fiscal formal (no maneja
depreciación acumulada NIIF, impuestos diferidos, etc.) — es la vista
gerencial de "ingresos menos todo lo que cuesta operar", pensada para
decisiones del día a día, no para declaraciones fiscales.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src import payroll
from src.money import format_money, get_currency
from src.session_utils import read_list as _rows

CANCELLED_STATUSES = {"Cancelado", "Cancelada", "Anulado", "Anulada"}


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


# ---------------------------------------------------------------------------
# Cálculo puro (testeable sin base de datos)
# ---------------------------------------------------------------------------

def revenue_for_month(sales: list[dict], month: str) -> float:
    return sum(
        _number(item.get("total"))
        for item in sales
        if _record_month(item) == month and item.get("order_status") not in CANCELLED_STATUSES
    )


def cogs_for_month(sales: list[dict], month: str) -> float:
    """Costo de ventas: usa estimated_cost si el registro de venta lo trae
    (ver bom_costing.py / sales_registry), 0 si no está disponible."""
    return sum(
        _number(item.get("estimated_cost"))
        for item in sales
        if _record_month(item) == month and item.get("order_status") not in CANCELLED_STATUSES
    )


def operating_expenses_for_month(expenses: list[dict], month: str) -> float:
    return sum(
        _number(item.get("amount"))
        for item in expenses
        if str(item.get("expense_date", ""))[:7] == month
    )


def operating_expenses_by_category(expenses: list[dict], month: str) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for item in expenses:
        if str(item.get("expense_date", ""))[:7] == month:
            totals[str(item.get("category") or "Otro")] += _number(item.get("amount"))
    return dict(totals)


def payroll_cost_for_month(entries_with_period_start: list[dict], month: str) -> float:
    """Recibe recibos de nómina ya combinados con el mes de inicio de su
    período (ver _payroll_entries_with_month), para no acoplar este módulo
    puro a la base de datos."""
    return sum(
        _number(item.get("base_salary")) + _number(item.get("bonuses_total")) - _number(item.get("deductions_total"))
        for item in entries_with_period_start
        if item.get("period_month") == month
    )


@dataclass(frozen=True)
class IncomeStatement:
    month: str
    revenue: float
    cogs: float
    gross_profit: float
    operating_expenses: float
    payroll_cost: float
    net_profit: float

    @property
    def gross_margin_percent(self) -> float:
        return (self.gross_profit / self.revenue * 100) if self.revenue else 0.0

    @property
    def net_margin_percent(self) -> float:
        return (self.net_profit / self.revenue * 100) if self.revenue else 0.0


def build_income_statement(sales: list[dict], expenses: list[dict], payroll_entries_with_month: list[dict], month: str) -> IncomeStatement:
    revenue = revenue_for_month(sales, month)
    cogs = cogs_for_month(sales, month)
    gross_profit = revenue - cogs
    opex = operating_expenses_for_month(expenses, month)
    payroll_cost = payroll_cost_for_month(payroll_entries_with_month, month)
    net_profit = gross_profit - opex - payroll_cost
    return IncomeStatement(
        month=month,
        revenue=revenue,
        cogs=cogs,
        gross_profit=gross_profit,
        operating_expenses=opex,
        payroll_cost=payroll_cost,
        net_profit=net_profit,
    )


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def _payroll_entries_with_month() -> list[dict]:
    """Combina cada recibo de nómina con el mes de inicio de su período,
    para poder filtrar por mes igual que ventas y gastos."""
    periods_by_id = {period["period_id"]: period for period in payroll.list_periods()}
    entries: list[dict] = []
    for period in periods_by_id.values():
        for entry in payroll.entries_for_period(period["period_id"]):
            entry = dict(entry)
            entry["period_month"] = str(period.get("period_start", ""))[:7]
            entries.append(entry)
    return entries


def render_income_statement() -> None:
    render_page_header("Estado de Resultados", "Ingresos, costo de ventas, gastos operativos y nómina consolidados por mes.")
    st.caption("Vista gerencial (ingresos − todo lo que cuesta operar), no un estado de resultados fiscal/contable formal.")

    sales = [item for item in _rows("sales_registry")]
    expenses = _rows("expense_records")
    payroll_entries = _payroll_entries_with_month()
    currency = get_currency()

    available_months = sorted({_record_month(item) for item in sales if _record_month(item)}, reverse=True)
    current_month = date.today().strftime("%Y-%m")
    if current_month not in available_months:
        available_months = [current_month] + available_months

    selected_month = st.selectbox("Mes", available_months, index=0)
    statement = build_income_statement(sales, expenses, payroll_entries, selected_month)

    cols = st.columns(3)
    cols[0].metric("Ingresos", format_money(statement.revenue, currency))
    cols[1].metric("Costo de ventas", format_money(statement.cogs, currency))
    cols[2].metric("Utilidad bruta", format_money(statement.gross_profit, currency))

    cols2 = st.columns(3)
    cols2[0].metric("Gastos operativos", format_money(statement.operating_expenses, currency))
    cols2[1].metric("Nómina", format_money(statement.payroll_cost, currency))
    cols2[2].metric("Utilidad neta", format_money(statement.net_profit, currency))

    cols3 = st.columns(2)
    cols3[0].metric("Margen bruto", f"{statement.gross_margin_percent:,.1f}%")
    cols3[1].metric("Margen neto", f"{statement.net_margin_percent:,.1f}%")

    if statement.net_profit < 0:
        st.error("El negocio tuvo pérdida neta este mes: los costos, gastos y nómina superaron los ingresos.")
    elif statement.net_margin_percent < 10:
        st.warning("El margen neto está por debajo del 10%. Vale la pena revisar precios, costos o gastos.")
    else:
        st.success("El negocio tuvo utilidad neta positiva este mes.")

    st.markdown("### Gastos operativos por categoría")
    by_category = operating_expenses_by_category(expenses, selected_month)
    if by_category:
        category_cols = st.columns(min(len(by_category), 5))
        for index, (category, amount) in enumerate(sorted(by_category.items(), key=lambda item: item[1], reverse=True)):
            category_cols[index % len(category_cols)].metric(category, format_money(amount, currency))
    else:
        st.info("No hay gastos operativos registrados este mes.")

    st.markdown("### Tendencia de seis meses")
    trend_rows = []
    for offset in range(-5, 1):
        month = _shift_month(selected_month, offset)
        row_statement = build_income_statement(sales, expenses, payroll_entries, month)
        trend_rows.append({
            "Mes": month,
            "Ingresos": row_statement.revenue,
            "Costo de ventas": row_statement.cogs,
            "Gastos operativos": row_statement.operating_expenses,
            "Nómina": row_statement.payroll_cost,
            "Utilidad neta": row_statement.net_profit,
        })
    st.dataframe(trend_rows, use_container_width=True, hide_index=True)

    render_info_card(
        "Alcance",
        "Ingresos = ventas facturadas del mes (sin cancelar). Costo de ventas usa el costo estimado de cada venta cuando está disponible. No reemplaza un estado de resultados fiscal/contable formal.",
        "P&L",
    )


app_shell.FUNCTIONAL_MODULES["Estado de Resultados"] = render_income_statement
