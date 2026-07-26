"""Integración no destructiva del tablero ejecutivo y accesos del Inicio."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from src import app_shell
from src.components import render_page_header
from src.executive_dashboard_domain import (
    approval_trace,
    capacity_usage,
    delivery_performance,
    net_margin,
    product_profitability,
    sales_period_comparison,
    top_customers,
    waste_by_process,
)
from src.money import format_money
from src.session_utils import read_list as _rows


def canonical_area_for_page(page: str, groups: dict[str, tuple[str, ...]] | None = None) -> str | None:
    for area, pages in (groups or app_shell.navigation_groups()).items():
        if page in pages:
            return area
    return None


def canonical_home_shortcuts() -> tuple[tuple[str, str, str, str], ...]:
    shortcuts = []
    for title, description, _legacy_area, page in app_shell._home_shortcuts_original():
        area = canonical_area_for_page(page)
        if area:
            shortcuts.append((title, description, area, page))
    return tuple(shortcuts)


def activate_home_navigation_fix() -> None:
    if not hasattr(app_shell, "_home_shortcuts_original"):
        app_shell._home_shortcuts_original = app_shell._home_shortcuts
    app_shell._home_shortcuts = canonical_home_shortcuts


def _executive_values() -> dict:
    sales = _rows("sales_registry")
    customers = _rows("customers_registry")
    orders = _rows("production_orders") or sales
    waste = _rows("production_waste_records")
    today = date.today()
    current_start = today - timedelta(days=29)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=29)
    return {
        "profitability": product_profitability(sales),
        "margin": net_margin(sales, sum(float(x.get("amount", 0) or 0) for x in _rows("expense_records"))),
        "customers": top_customers(sales, customers),
        "comparison": sales_period_comparison(sales, current_start, today, previous_start, previous_end),
        "delivery": delivery_performance(orders, today),
        "capacity": capacity_usage(orders),
        "waste": waste_by_process(waste),
        "approvals": approval_trace(_rows("purchases_registry"), _rows("inventory_adjustments"), _rows("price_change_history"), _rows("payables_registry")),
    }


def render_executive_dashboard() -> None:
    values = _executive_values()
    render_page_header("Tablero ejecutivo", "Rentabilidad, operación y trazabilidad para decidir con datos reales.")
    margin = values["margin"]
    comparison = values["comparison"]
    delivery = values["delivery"]
    capacity = values["capacity"]
    metrics = st.columns(4)
    metrics[0].metric("Ventas netas", format_money(margin["revenue"]))
    metrics[1].metric("Margen neto", f"{margin['net_margin_pct']:.1f}%", format_money(margin["net_profit"]))
    metrics[2].metric("Ventas vs. período anterior", f"{comparison['variation_pct']:.1f}%", format_money(comparison["variation"]))
    metrics[3].metric("Pedidos a tiempo", f"{delivery['on_time_pct']:.1f}%", f"{delivery['late']} atrasado(s)")

    financial, operations, approvals = st.tabs(("Rentabilidad", "Operación", "Aprobaciones"))
    with financial:
        st.markdown("### Rentabilidad por producto o servicio")
        st.dataframe(values["profitability"], use_container_width=True, hide_index=True)
        st.markdown("### Top clientes")
        st.dataframe(values["customers"], use_container_width=True, hide_index=True)
    with operations:
        cards = st.columns(3)
        cards[0].metric("Capacidad usada", f"{capacity['usage_pct']:.1f}%")
        cards[1].metric("Pedidos atrasados", str(delivery["late"]))
        cards[2].metric("Pedidos pendientes", str(delivery["pending"]))
        st.markdown("### Mermas por proceso")
        st.dataframe(values["waste"], use_container_width=True, hide_index=True)
    with approvals:
        st.markdown("### Quién aprobó compras, ajustes y cambios de precio")
        st.dataframe(values["approvals"], use_container_width=True, hide_index=True)


def activate_executive_dashboard() -> None:
    activate_home_navigation_fix()
    app_shell.FUNCTIONAL_MODULES["Panel comercial"] = render_executive_dashboard
    app_shell.FUNCTIONAL_MODULES["Panel financiero y cierres"] = render_executive_dashboard
