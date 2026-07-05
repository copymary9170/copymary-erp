"""Metas mensuales para CopyMary ERP."""

from datetime import date

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def render_business_goals() -> None:
    with st.container(border=True):
        render_page_header("Metas del negocio", "Define objetivos mensuales y revisa el avance real.")
        st.caption("Las metas se calculan con ventas y movimientos registrados en la sesión.")

    goals = dict(st.session_state.get("business_goals", {}))
    month = date.today().strftime("%Y-%m")

    with st.form("business_goals_form"):
        columns = st.columns(3)
        sales_goal = columns[0].number_input(
            "Meta de ventas",
            min_value=0.0,
            value=float(goals.get("sales_goal", 0.0)),
            step=10.0,
        )
        profit_goal = columns[1].number_input(
            "Meta de ganancia",
            min_value=0.0,
            value=float(goals.get("profit_goal", 0.0)),
            step=10.0,
        )
        orders_goal = columns[2].number_input(
            "Meta de pedidos",
            min_value=0,
            value=int(goals.get("orders_goal", 0)),
            step=1,
        )
        submitted = st.form_submit_button("Guardar metas", type="primary", use_container_width=True)

    if submitted:
        st.session_state["business_goals"] = {
            "month": month,
            "sales_goal": float(sales_goal),
            "profit_goal": float(profit_goal),
            "orders_goal": int(orders_goal),
        }
        st.success("Metas actualizadas.")
        st.rerun()

    sales = [sale for sale in _rows("sales_registry") if sale.get("order_status") != "Cancelado"]
    total_sales = sum(float(sale.get("total", 0.0)) for sale in sales)
    total_profit = sum(float(sale.get("total", 0.0)) - float(sale.get("estimated_cost", 0.0)) for sale in sales)
    total_orders = len(sales)

    metrics = st.columns(3)
    metrics[0].metric("Ventas actuales", format_money(total_sales))
    metrics[1].metric("Ganancia estimada", format_money(total_profit))
    metrics[2].metric("Pedidos", str(total_orders))

    for label, current, target in (
        ("Ventas", total_sales, float(goals.get("sales_goal", 0.0))),
        ("Ganancia", total_profit, float(goals.get("profit_goal", 0.0))),
        ("Pedidos", float(total_orders), float(goals.get("orders_goal", 0))),
    ):
        with st.container(border=True):
            st.markdown(f"### {label}")
            if target <= 0:
                st.info("Aún no has definido esta meta.")
            else:
                progress = min(max(current / target, 0.0), 1.0)
                st.progress(progress)
                st.caption(f"Avance: {progress * 100:,.1f}%")

    render_info_card("Periodo", f"Metas activas para {month}.", "SEGUIMIENTO MENSUAL")
