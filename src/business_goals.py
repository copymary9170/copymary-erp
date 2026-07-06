"""Metas mensuales y planificación de crecimiento para CopyMary ERP."""

from calendar import monthrange
from datetime import date, datetime

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_goals(raw) -> dict[str, dict]:
    if not isinstance(raw, dict):
        return {}
    if "month" in raw:
        month = str(raw.get("month", ""))
        if not month:
            return {}
        return {
            month: {
                "sales_goal": _number(raw.get("sales_goal")),
                "profit_goal": _number(raw.get("profit_goal")),
                "orders_goal": int(_number(raw.get("orders_goal"))),
                "notes": str(raw.get("notes", "")),
            }
        }
    normalized: dict[str, dict] = {}
    for month, values in raw.items():
        if isinstance(values, dict):
            normalized[str(month)] = {
                "sales_goal": _number(values.get("sales_goal")),
                "profit_goal": _number(values.get("profit_goal")),
                "orders_goal": int(_number(values.get("orders_goal"))),
                "notes": str(values.get("notes", "")),
            }
    return normalized


def _record_month(record: dict) -> str:
    raw = str(record.get("created_at_utc", record.get("created_at", record.get("date", ""))))
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return raw[:7] if len(raw) >= 7 else ""


def _month_options(goals: dict[str, dict], sales: list[dict]) -> list[str]:
    current = date.today().strftime("%Y-%m")
    months = {current, *goals.keys()}
    months.update(filter(None, (_record_month(sale) for sale in sales)))
    return sorted(months, reverse=True)


def _previous_month(month: str) -> str:
    year, number = (int(part) for part in month.split("-"))
    if number == 1:
        return f"{year - 1}-12"
    return f"{year}-{number - 1:02d}"


def _period_results(sales: list[dict], month: str) -> tuple[float, float, int]:
    period_sales = [sale for sale in sales if _record_month(sale) == month]
    total_sales = sum(_number(sale.get("total")) for sale in period_sales)
    total_profit = sum(
        _number(sale.get("total")) - _number(sale.get("estimated_cost"))
        for sale in period_sales
    )
    return total_sales, total_profit, len(period_sales)


def _month_timing(month: str) -> tuple[int, int, int]:
    year, number = (int(part) for part in month.split("-"))
    days = monthrange(year, number)[1]
    current = date.today()
    if (year, number) < (current.year, current.month):
        return days, days, 0
    if (year, number) > (current.year, current.month):
        return 0, days, days
    elapsed = current.day
    return elapsed, days, max(days - elapsed, 0)


def _goal_status(current: float, target: float, elapsed: int, total_days: int) -> tuple[str, float, float]:
    if target <= 0:
        return "Sin meta", 0.0, 0.0
    progress = max(current / target, 0.0)
    expected = elapsed / total_days if total_days else 0.0
    if progress >= 1:
        status = "Superada"
    elif progress + 0.05 >= expected:
        status = "En ritmo"
    elif progress + 0.15 >= expected:
        status = "En riesgo"
    else:
        status = "Atrasada"
    return status, progress, expected


def _render_goal_card(label: str, current: float, target: float, elapsed: int, total_days: int, remaining_days: int, money: bool = True) -> None:
    status, progress, expected = _goal_status(current, target, elapsed, total_days)
    with st.container(border=True):
        top = st.columns([2, 1])
        top[0].markdown(f"### {label}")
        top[1].metric("Estado", status)
        if target <= 0:
            st.info("Aún no has definido esta meta para el mes seleccionado.")
            return
        st.progress(min(progress, 1.0))
        value = format_money(current) if money else f"{int(current)}"
        target_value = format_money(target) if money else f"{int(target)}"
        st.caption(f"Actual: {value} · Meta: {target_value} · Avance: {progress * 100:,.1f}%")
        if remaining_days > 0 and current < target:
            daily_needed = (target - current) / remaining_days
            daily_text = format_money(daily_needed) if money else f"{daily_needed:,.1f} pedido(s)"
            st.warning(f"Necesitas aproximadamente {daily_text} por día durante los próximos {remaining_days} días.")
        elif current >= target:
            difference = current - target
            difference_text = format_money(difference) if money else f"{int(difference)}"
            st.success(f"Meta superada por {difference_text}.")
        if elapsed > 0 and elapsed < total_days:
            forecast = current / elapsed * total_days
            forecast_text = format_money(forecast) if money else f"{forecast:,.1f}"
            st.caption(f"Proyección al cierre: {forecast_text} · Ritmo esperado hoy: {expected * 100:,.1f}%")


def render_business_goals() -> None:
    render_page_header(
        "Metas del negocio",
        "Define objetivos mensuales, mide el ritmo real y convierte cada meta en un plan de acción.",
    )
    st.caption("Cada período utiliza únicamente las ventas registradas dentro del mes correspondiente.")

    cancelled = {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    sales = [sale for sale in _rows("sales_registry") if sale.get("order_status") not in cancelled]
    goals_by_month = _normalize_goals(st.session_state.get("business_goals", {}))
    month = st.selectbox("Mes de seguimiento", _month_options(goals_by_month, sales))
    current_goals = goals_by_month.get(month, {})

    previous = _previous_month(month)
    previous_goals = goals_by_month.get(previous, {})
    if previous_goals and month not in goals_by_month:
        if st.button("Copiar metas del mes anterior", use_container_width=True):
            goals_by_month[month] = dict(previous_goals)
            st.session_state["business_goals"] = goals_by_month
            st.rerun()

    with st.expander("Definir o actualizar metas", expanded=not bool(current_goals)):
        with st.form("business_goals_form"):
            columns = st.columns(3)
            sales_goal = columns[0].number_input(
                "Meta de ventas",
                min_value=0.0,
                value=_number(current_goals.get("sales_goal")),
                step=10.0,
            )
            profit_goal = columns[1].number_input(
                "Meta de ganancia",
                min_value=0.0,
                value=_number(current_goals.get("profit_goal")),
                step=10.0,
            )
            orders_goal = columns[2].number_input(
                "Meta de pedidos",
                min_value=0,
                value=int(_number(current_goals.get("orders_goal"))),
                step=1,
            )
            notes = st.text_area(
                "Plan o enfoque del mes",
                value=str(current_goals.get("notes", "")),
                placeholder="Ejemplo: impulsar papelería creativa, captar clientes escolares y reducir gastos.",
            )
            submitted = st.form_submit_button("Guardar metas del mes", type="primary", use_container_width=True)

    if submitted:
        goals_by_month[month] = {
            "sales_goal": float(sales_goal),
            "profit_goal": float(profit_goal),
            "orders_goal": int(orders_goal),
            "notes": notes.strip(),
        }
        st.session_state["business_goals"] = goals_by_month
        st.success("Metas mensuales actualizadas.")
        st.rerun()

    total_sales, total_profit, total_orders = _period_results(sales, month)
    previous_sales, previous_profit, previous_orders = _period_results(sales, previous)
    elapsed, total_days, remaining_days = _month_timing(month)

    metrics = st.columns(4)
    metrics[0].metric(
        "Ventas del mes",
        format_money(total_sales),
        format_money(total_sales - previous_sales) if previous_sales else None,
    )
    metrics[1].metric(
        "Ganancia estimada",
        format_money(total_profit),
        format_money(total_profit - previous_profit) if previous_profit else None,
    )
    metrics[2].metric(
        "Pedidos",
        str(total_orders),
        str(total_orders - previous_orders) if previous_orders else None,
    )
    metrics[3].metric("Días restantes", str(remaining_days))

    if current_goals.get("notes"):
        render_info_card("Enfoque del mes", str(current_goals["notes"]), "PLAN COMERCIAL")

    st.markdown("### Avance y ritmo necesario")
    goal_columns = st.columns(3)
    with goal_columns[0]:
        _render_goal_card("Ventas", total_sales, _number(current_goals.get("sales_goal")), elapsed, total_days, remaining_days)
    with goal_columns[1]:
        _render_goal_card("Ganancia", total_profit, _number(current_goals.get("profit_goal")), elapsed, total_days, remaining_days)
    with goal_columns[2]:
        _render_goal_card("Pedidos", float(total_orders), _number(current_goals.get("orders_goal")), elapsed, total_days, remaining_days, money=False)

    st.markdown("### Recomendaciones automáticas")
    recommendations: list[str] = []
    sales_target = _number(current_goals.get("sales_goal"))
    profit_target = _number(current_goals.get("profit_goal"))
    orders_target = _number(current_goals.get("orders_goal"))
    sales_status, _, _ = _goal_status(total_sales, sales_target, elapsed, total_days)
    profit_status, _, _ = _goal_status(total_profit, profit_target, elapsed, total_days)
    orders_status, _, _ = _goal_status(float(total_orders), orders_target, elapsed, total_days)

    if sales_status in {"Atrasada", "En riesgo"}:
        recommendations.append("Revisa cotizaciones pendientes y concentra promociones en los servicios con mayor demanda.")
    if profit_status in {"Atrasada", "En riesgo"}:
        recommendations.append("Revisa costos, descuentos y productos con margen bajo antes de aumentar el volumen de ventas.")
    if orders_status in {"Atrasada", "En riesgo"}:
        recommendations.append("Activa seguimiento a clientes anteriores y crea ofertas de entrada para aumentar la cantidad de pedidos.")
    if total_sales > 0 and total_profit / total_sales < 0.30:
        recommendations.append("El margen estimado está por debajo de 30%; prioriza productos rentables y ajusta precios cuando sea necesario.")
    if not recommendations:
        recommendations.append("El mes avanza de acuerdo con las metas definidas. Mantén el ritmo y revisa nuevamente en pocos días.")
    for recommendation in recommendations:
        st.info(recommendation)

    if goals_by_month:
        st.markdown("### Historial de metas")
        for history_month in sorted(goals_by_month, reverse=True):
            values = goals_by_month[history_month]
            actual_sales, actual_profit, actual_orders = _period_results(sales, history_month)
            with st.expander(history_month, expanded=history_month == month):
                columns = st.columns(3)
                columns[0].metric("Ventas", format_money(actual_sales), f"Meta {format_money(_number(values.get('sales_goal')))}")
                columns[1].metric("Ganancia", format_money(actual_profit), f"Meta {format_money(_number(values.get('profit_goal')))}")
                columns[2].metric("Pedidos", str(actual_orders), f"Meta {int(_number(values.get('orders_goal')))}")
                if values.get("notes"):
                    st.caption(str(values["notes"]))

    render_info_card(
        "Seguimiento mensual",
        f"Resultados, proyección y ritmo requerido para {month}.",
        "METAS DEL NEGOCIO",
    )
