"""Inicio fase 6B: visualización de metas persistentes y KPI.

El módulo calcula indicadores de solo lectura sobre colecciones existentes y
resuelve las metas aplicables mediante la capa de servicio. No modifica ventas,
compras, inventario, producción o finanzas.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

from src.auth import current_user
from src.home_kpi_registry import KPI_DEFINITIONS, KPIDefinition
from src.home_persistent_goals import DashboardGoalSet, resolve_dashboard_goals
from src.session_utils import read_list


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _row_date(row: dict) -> date | None:
    for key in ("created_at_utc", "created_at", "date", "sale_date", "movement_date", "updated_at_utc"):
        parsed = _date_value(row.get(key))
        if parsed:
            return parsed
    return None


def _amount(row: dict) -> float:
    return _num(row.get("total", row.get("grand_total", row.get("amount", row.get("value", 0.0)))))


def _current_month(rows: list[dict]) -> list[dict]:
    today = date.today()
    return [row for row in rows if (parsed := _row_date(row)) and parsed.year == today.year and parsed.month == today.month]


def _monthly_sales() -> float:
    return sum(_amount(row) for row in _current_month(read_list("sales_registry")))


def _monthly_collections() -> float:
    total = 0.0
    accepted = {"ingreso", "entrada", "cobro", "venta", "income"}
    for row in _current_month(read_list("cash_movements")):
        movement_type = str(row.get("movement_type", row.get("type", ""))).strip().casefold()
        if movement_type in accepted:
            total += abs(_num(row.get("amount", row.get("value", 0.0))))
    return total


def _quote_conversion() -> float:
    rows = _current_month(read_list("quotes_registry"))
    if not rows:
        return 0.0
    accepted = {"aceptada", "aceptado", "convertida", "convertido"}
    converted = sum(str(row.get("status", "")).strip().casefold() in accepted for row in rows)
    return converted / len(rows) * 100


def _on_time_delivery() -> float:
    completed = []
    for row in _current_month(read_list("sales_registry")):
        status = str(row.get("order_status", row.get("status", ""))).strip().casefold()
        if status not in {"entregado", "entregada", "completado", "completada"}:
            continue
        due = _date_value(row.get("delivery_date") or row.get("due_date") or row.get("expected_date"))
        delivered = _date_value(row.get("delivered_at") or row.get("completed_at") or row.get("updated_at_utc"))
        if due and delivered:
            completed.append(delivered <= due)
    return sum(completed) / len(completed) * 100 if completed else 0.0


def _healthy_inventory() -> float:
    active = [row for row in read_list("inventory_registry") if row.get("active", True)]
    if not active:
        return 0.0
    healthy = 0
    for row in active:
        quantity = _num(row.get("available_quantity", row.get("quantity", row.get("stock", 0.0))))
        minimum = _num(row.get("minimum_stock", row.get("reorder_point", 0.0)))
        if quantity > 0 and (minimum <= 0 or quantity > minimum):
            healthy += 1
    return healthy / len(active) * 100


def _overdue_receivables() -> float:
    today = date.today()
    total = 0.0
    terminal = {"pagado", "pagada", "cerrado", "cerrada", "cancelado", "cancelada"}
    for row in read_list("receivables_registry"):
        if str(row.get("status", "Pendiente")).strip().casefold() in terminal:
            continue
        due = _date_value(row.get("due_date") or row.get("payment_due_date") or row.get("expires_at"))
        if due and due < today:
            total += max(_num(row.get("balance", row.get("pending_amount", row.get("amount_due", 0.0)))), 0.0)
    return total


_CALCULATORS = {
    "monthly_sales": _monthly_sales,
    "monthly_collections": _monthly_collections,
    "quote_conversion": _quote_conversion,
    "on_time_delivery": _on_time_delivery,
    "healthy_inventory": _healthy_inventory,
    "overdue_receivables_limit": _overdue_receivables,
}


def _format(value: float, unit: str) -> str:
    if unit == "currency":
        return f"${value:,.2f}"
    if unit == "percent":
        return f"{value:,.1f}%"
    return f"{value:,.0f}"


def _progress(definition: KPIDefinition, current: float, target: float) -> float:
    if definition.direction == "lower":
        if target <= 0:
            return 1.0 if current <= 0 else 0.0
        if current <= target:
            return 1.0
        return max(target / current, 0.0)
    if target <= 0:
        return 1.0 if current >= 0 else 0.0
    return max(current / target, 0.0)


def _status(definition: KPIDefinition, current: float, target: float) -> str:
    ratio = _progress(definition, current, target)
    if ratio >= 1:
        return "Cumplido"
    if ratio >= 0.75:
        return "En curso"
    if ratio >= 0.5:
        return "En riesgo"
    return "Crítico"


def _difference(definition: KPIDefinition, current: float, target: float) -> float:
    if definition.direction == "lower":
        return max(current - target, 0.0)
    return max(target - current, 0.0)


def _scope_label(goal: dict[str, Any] | None) -> str:
    if not goal:
        return "Valor predeterminado"
    scope = str(goal.get("scope_type") or "company")
    labels = {"user": "Meta personal", "role": "Meta heredada por rol", "company": "Meta de empresa"}
    return labels.get(scope, "Meta persistente")


def _resolve_goal_set(user_id: str) -> DashboardGoalSet:
    user = current_user()
    if not user:
        return resolve_dashboard_goals(user_id=user_id, role_id="", role_name="Sin rol")
    return resolve_dashboard_goals(
        user_id=user.user_id,
        role_id=user.role_id,
        role_name=user.role_name,
    )


def render_phase6_sections(user_id: str) -> None:
    """Renderiza metas persistentes sin habilitar edición desde Inicio."""
    goal_set = _resolve_goal_set(user_id)
    goals = goal_set.targets

    st.markdown("### Metas y KPI")
    if goal_set.source == "persistent":
        st.caption("Metas persistentes aplicables al usuario autenticado. La edición se realiza desde el gestor de metas.")
    elif goal_set.message:
        st.info(goal_set.message)

    results = []
    for definition in KPI_DEFINITIONS:
        current = _CALCULATORS[definition.key]()
        target = goals[definition.key]
        progress = _progress(definition, current, target)
        results.append((definition, current, target, progress, _status(definition, current, target)))

    summary = st.columns(4)
    summary[0].metric("Metas cumplidas", sum(status == "Cumplido" for *_, status in results))
    summary[1].metric("En curso", sum(status == "En curso" for *_, status in results))
    summary[2].metric("En riesgo", sum(status == "En riesgo" for *_, status in results))
    summary[3].metric("Críticas", sum(status == "Crítico" for *_, status in results))

    columns = st.columns(2)
    for index, (definition, current, target, progress, status) in enumerate(results):
        goal = goal_set.persistent_goals.get(definition.key)
        with columns[index % 2]:
            with st.container(border=True):
                st.markdown(f"#### {definition.label}")
                st.metric("Actual", _format(current, definition.unit))
                st.progress(min(progress, 1.0), text=f"Cumplimiento: {progress * 100:.1f}% · {status}")
                st.caption(
                    f"Meta: {_format(target, definition.unit)} · "
                    f"Brecha: {_format(_difference(definition, current, target), definition.unit)} · "
                    f"Periodo: {definition.period}"
                )
                st.caption(f"{_scope_label(goal)} · Origen KPI: {definition.source}. {definition.description}")
                if goal:
                    st.caption(
                        f"Vigencia: {goal.get('start_date', '—')} → {goal.get('due_date', '—')} · "
                        f"Versión {goal.get('version', 1)}"
                    )

    critical = [definition.label for definition, _, _, _, status in results if status == "Crítico"]
    risk = [definition.label for definition, _, _, _, status in results if status == "En riesgo"]
    with st.container(border=True):
        st.markdown("#### Lectura de cumplimiento")
        if critical:
            st.warning("Prioridad inmediata: " + ", ".join(critical) + ".")
        elif risk:
            st.info("Revisar antes del cierre del periodo: " + ", ".join(risk) + ".")
        else:
            st.success("Las metas se encuentran cumplidas o avanzan dentro del rango esperado.")
        st.caption("Lectura determinista. Inicio consulta metas y datos operativos en modo de solo lectura.")
