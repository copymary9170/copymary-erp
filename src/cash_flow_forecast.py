"""Flujo de caja proyectado unificado para CopyMary ERP.

Tercer gap de la revisión de negocio (dueña + finanzas + producción):
existían proyecciones sueltas (cartera por cobrar con vencimientos en
accounts_receivable.py, presupuesto de gastos en expenses_budget.py) pero
ninguna vista consolidada que responda la pregunta real de una dueña de
negocio: "¿cuánto efectivo voy a tener en 30/60/90 días?".

No inventa fuentes de datos: reutiliza cash_movements (posición actual),
receivables_registry + sales_registry (cobros esperados, con fecha de
vencimiento), payables_registry + purchases_registry (pagos esperados a
proveedores), recurring_expenses (gastos recurrentes), y employees (nómina
activa, según payment_frequency).

Es una proyección, no una promesa: asume que las cuentas por cobrar/pagar se
cobran/pagan en su fecha de vencimiento, que los gastos recurrentes se
repiten cada mes, y que la nómina activa se mantiene igual. Sirve para
anticipar problemas de liquidez, no para contabilidad formal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import streamlit as st

from src import app_shell, payroll
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import read_list as _rows

PAYMENTS_PER_MONTH = {"Mensual": 1, "Quincenal": 2, "Semanal": 4}


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _meta_for(record_id: str, id_field: str, metadata: list[dict]) -> dict:
    for item in metadata:
        if str(item.get(id_field, "")) == record_id:
            return dict(item)
    return {}


def _paid_amount(record_id: str, id_field: str, total: float, payments: list[dict]) -> float:
    explicit = sum(_number(item.get("amount")) for item in payments if str(item.get(id_field, "")) == record_id)
    return min(explicit, total) if explicit > 0 else 0.0


# ---------------------------------------------------------------------------
# Cálculo puro (testeable sin base de datos)
# ---------------------------------------------------------------------------

def current_cash_position(cash_movements: list[dict]) -> float:
    income = sum(_number(item.get("amount")) for item in cash_movements if item.get("movement_type") == "Ingreso")
    expenses = sum(_number(item.get("amount")) for item in cash_movements if item.get("movement_type") == "Egreso")
    return income - expenses


def expected_receivables(sales: list[dict], payments: list[dict], metadata: list[dict], as_of: date, horizon_days: int) -> float:
    """Suma de saldos pendientes de venta con vencimiento dentro del horizonte
    (incluye vencidos: due_date <= as_of + horizon_days, sin límite inferior,
    porque una cuenta vencida sigue siendo dinero que se espera cobrar)."""
    cutoff = as_of + timedelta(days=horizon_days)
    total = 0.0
    for sale in sales:
        sale_id = str(sale.get("sale_id", ""))
        meta = _meta_for(sale_id, "sale_id", metadata)
        due_date_raw = meta.get("due_date")
        if not due_date_raw:
            continue
        try:
            due_date = date.fromisoformat(str(due_date_raw))
        except ValueError:
            continue
        if due_date > cutoff:
            continue
        balance = _number(sale.get("total")) - _paid_amount(sale_id, "sale_id", _number(sale.get("total")), payments)
        total += max(balance, 0.0)
    return total


def expected_payables(purchases: list[dict], payments: list[dict], metadata: list[dict], as_of: date, horizon_days: int) -> float:
    cutoff = as_of + timedelta(days=horizon_days)
    total = 0.0
    for purchase in purchases:
        purchase_id = str(purchase.get("purchase_id", ""))
        meta = _meta_for(purchase_id, "purchase_id", metadata)
        due_date_raw = meta.get("due_date")
        if not due_date_raw:
            continue
        try:
            due_date = date.fromisoformat(str(due_date_raw))
        except ValueError:
            continue
        if due_date > cutoff:
            continue
        balance = _number(purchase.get("total")) - _paid_amount(purchase_id, "purchase_id", _number(purchase.get("total")), payments)
        total += max(balance, 0.0)
    return total


def expected_recurring_expenses(recurring: list[dict], horizon_days: int) -> float:
    """Aproxima: cada gasto recurrente se repite una vez por mes calendario
    dentro del horizonte (30 días ~ 1 mes, 60 ~ 2, 90 ~ 3)."""
    months = max(round(horizon_days / 30), 1)
    return sum(_number(item.get("amount")) for item in recurring) * months


def expected_payroll_cost(employees: list[dict], horizon_days: int) -> float:
    """Nómina activa proyectada: salario base x cantidad de pagos esperados
    en el horizonte, según la frecuencia de pago de cada empleado."""
    months = max(horizon_days / 30, 1 / 30)
    total = 0.0
    for employee in employees:
        if employee.get("status") != "active":
            continue
        payments_per_month = PAYMENTS_PER_MONTH.get(employee.get("payment_frequency"), 1)
        total += _number(employee.get("base_salary")) * payments_per_month * months
    return total


@dataclass(frozen=True)
class CashFlowForecast:
    horizon_days: int
    current_cash: float
    expected_inflows: float
    expected_outflows: float

    @property
    def projected_cash(self) -> float:
        return self.current_cash + self.expected_inflows - self.expected_outflows


def build_forecast(cash_movements: list[dict], sales: list[dict], customer_payments: list[dict], receivables_metadata: list[dict], purchases: list[dict], supplier_payments: list[dict], payables_metadata: list[dict], recurring_expenses: list[dict], employees: list[dict], horizon_days: int, as_of: date | None = None) -> CashFlowForecast:
    as_of = as_of or date.today()
    current_cash = current_cash_position(cash_movements)
    inflows = expected_receivables(sales, customer_payments, receivables_metadata, as_of, horizon_days)
    outflows = (
        expected_payables(purchases, supplier_payments, payables_metadata, as_of, horizon_days)
        + expected_recurring_expenses(recurring_expenses, horizon_days)
        + expected_payroll_cost(employees, horizon_days)
    )
    return CashFlowForecast(horizon_days=horizon_days, current_cash=current_cash, expected_inflows=inflows, expected_outflows=outflows)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def render_cash_flow_forecast() -> None:
    render_page_header("Flujo de caja proyectado", "Posición de efectivo esperada a 30, 60 y 90 días.")
    st.caption("Proyección, no una promesa: asume que cuentas por cobrar/pagar se liquidan en su vencimiento, que los gastos recurrentes se repiten cada mes, y que la nómina activa se mantiene igual.")

    cash_movements = _rows("cash_movements")
    sales = _rows("sales_registry")
    customer_payments = _rows("payment_records")
    receivables_metadata = _rows("receivables_registry")
    purchases = _rows("purchases_registry")
    supplier_payments = _rows("supplier_payment_records")
    payables_metadata = _rows("payables_registry")
    recurring_expenses = _rows("recurring_expenses")
    employees = payroll.list_employees()
    currency = get_currency()

    current_cash = current_cash_position(cash_movements)
    st.metric("Posición de caja actual", format_money(current_cash, currency))

    forecasts = [
        build_forecast(cash_movements, sales, customer_payments, receivables_metadata, purchases, supplier_payments, payables_metadata, recurring_expenses, employees, horizon)
        for horizon in (30, 60, 90)
    ]

    cols = st.columns(3)
    for col, forecast in zip(cols, forecasts):
        col.metric(f"A {forecast.horizon_days} días", format_money(forecast.projected_cash, currency), delta=format_money(forecast.expected_inflows - forecast.expected_outflows, currency))

    worst_case = min(forecasts, key=lambda item: item.projected_cash)
    if worst_case.projected_cash < 0:
        st.error(f"La proyección a {worst_case.horizon_days} días muestra caja negativa ({format_money(worst_case.projected_cash, currency)}). Prioriza cobranza o negocia plazos de pago.")
    elif worst_case.projected_cash < current_cash * 0.3:
        st.warning("La caja proyectada cae significativamente respecto al nivel actual en alguno de los horizontes. Vale la pena revisar el detalle.")
    else:
        st.success("La proyección de caja no muestra una alerta crítica en los próximos 90 días.")

    st.markdown("### Detalle a 90 días")
    detail = forecasts[-1]
    detail_cols = st.columns(3)
    detail_cols[0].metric("Efectivo actual", format_money(detail.current_cash, currency))
    detail_cols[1].metric("Entradas esperadas (cobros)", format_money(detail.expected_inflows, currency))
    detail_cols[2].metric("Salidas esperadas (pagos + gastos + nómina)", format_money(detail.expected_outflows, currency))

    breakdown_cols = st.columns(3)
    breakdown_cols[0].metric("Cuentas por pagar", format_money(expected_payables(purchases, supplier_payments, payables_metadata, date.today(), 90), currency))
    breakdown_cols[1].metric("Gastos recurrentes (3 meses)", format_money(expected_recurring_expenses(recurring_expenses, 90), currency))
    breakdown_cols[2].metric("Nómina activa (3 meses)", format_money(expected_payroll_cost(employees, 90), currency))

    render_info_card(
        "Alcance",
        "Proyección basada en vencimientos registrados de cuentas por cobrar/pagar, gastos recurrentes definidos, y nómina activa. No sustituye un presupuesto financiero formal.",
        "FLUJO DE CAJA",
    )


app_shell.FUNCTIONAL_MODULES["Flujo de caja proyectado"] = render_cash_flow_forecast
