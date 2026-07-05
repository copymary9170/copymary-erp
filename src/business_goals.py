"""Metas mensuales con historial para CopyMary ERP."""

from datetime import date, datetime

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _normalize_goals(raw) -> dict[str, dict]:
    if not isinstance(raw, dict):
        return {}
    if "month" in raw:
        month = str(raw.get("month", ""))
        if not month:
            return {}
        return {
            month: {
                "sales_goal": float(raw.get("sales_goal", 0.0)),
                "profit_goal": float(raw.get("profit_goal", 0.0)),
                "orders_goal": int(raw.get("orders_goal", 0)),
            }
        }
    normalized: dict[str, dict] = {}
    for month, values in raw.items():
        if isinstance(values, dict):
            normalized[str(month)] = {
                "sales_goal": float(values.get("sales_goal", 0.0)),
                "profit_goal": float(values.get("profit_goal", 0.0)),
                "orders_goal": int(values.get("orders_goal", 0)),
            }
    return normalized


def _record_month(record: dict) -> str:
    raw = str(record.get("created_at_utc", ""))
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return raw[:7] if len(raw) >= 7 else ""


def _month_options(goals: dict[str, dict], sales: list[dict]) -> list[str]:
    current = date.today().strftime("%Y-%m")
    months = {current, *goals.keys()}
    months.update(filter(None, (_record_month(sale) for sale in sales)))
    return sorted(months, reverse=True)


def render_business_goals() -> None:
    with st.container(border=True):
        render_page_header("Metas del negocio", "Define objetivos por mes y conserva el historial de avance.")
        st.caption("Cada período usa únicamente las ventas registradas dentro de ese mismo mes.")

    sales = [sale for sale in _rows("sales_registry") if sale.get("order_status") != "Cancelado"]
    goals_by_month = _normalize_goals(st.session_state.get("business_goals", {}))
    month = st.selectbox("Mes de seguimiento", _month_options(goals_by_month, sales))
    current_goals = goals_by_month.get(month, {})

    with st.form("business_goals_form"):
        columns = st.columns(3)
        sales_goal = columns[0].number_input(
            "Meta de ventas",
            min_value=0.0,
            value=float(current_goals.get("sales_goal", 0.0)),
            step=10.0,
        )
        profit_goal = columns[1].number_input(
            "Meta de ganancia",
            min_value=0.0,
            value=float(current_goals.get("profit_goal", 0.0)),
            step=10.0,
        )
        orders_goal = columns[2].number_input(
            "Meta de pedidos",
            min_value=0,
            value=int(current_goals.get("orders_goal", 0)),
            step=1,
        )
        submitted = st.form_submit_button("Guardar metas del mes", type="primary", use_container_width=True)

    if submitted:
        goals_by_month[month] = {
            "sales_goal": float(sales_goal),
            "profit_goal": float(profit_goal),
            "orders_goal": int(orders_goal),
        }
        st.session_state["business_goals"] = goals_by_month
        st.success("Metas mensuales actualizadas.")
        st.rerun()

    period_sales = [sale for sale in sales if _record_month(sale) == month]
    total_sales = sum(float(sale.get("total", 0.0)) for sale in period_sales)
    total_profit = sum(
        float(sale.get("total", 0.0)) - float(sale.get("estimated_cost", 0.0))
        for sale in period_sales
    )
    total_orders = len(period_sales)

    metrics = st.columns(4)
    metrics[0].metric("Ventas del mes", format_money(total_sales))
    metrics[1].metric("Ganancia estimada", format_money(total_profit))
    metrics[2].metric("Pedidos", str(total_orders))
    metrics[3].metric("Meses con metas", str(len(goals_by_month)))

    for label, current, target in (
        ("Ventas", total_sales, float(current_goals.get("sales_goal", 0.0))),
        ("Ganancia", total_profit, float(current_goals.get("profit_goal", 0.0))),
        ("Pedidos", float(total_orders), float(current_goals.get("orders_goal", 0))),
    ):
        with st.container(border=True):
            st.markdown(f"### {label}")
            if target <= 0:
                st.info("Aún no has definido esta meta para el mes seleccionado.")
            else:
                progress = max(current / target, 0.0)
                st.progress(min(progress, 1.0))
                difference = current - target
                st.caption(
                    f"Avance: {progress * 100:,.1f}% · "
                    f"{'Superada por' if difference >= 0 else 'Falta'} {abs(difference):,.2f}"
                )

    if goals_by_month:
        st.subheader("Historial de metas")
        for history_month in sorted(goals_by_month, reverse=True):
            values = goals_by_month[history_month]
            st.write(
                f"**{history_month}** · Ventas {format_money(float(values.get('sales_goal', 0.0)))} · "
                f"Ganancia {format_money(float(values.get('profit_goal', 0.0)))} · "
                f"Pedidos {int(values.get('orders_goal', 0))}"
            )

    render_info_card("Periodo", f"Resultados y metas correspondientes a {month}.", "SEGUIMIENTO MENSUAL")
