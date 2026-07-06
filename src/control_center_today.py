"""Plan diario y creación rápida para el Centro de control."""

from datetime import date

import streamlit as st

from src import control_center as base
from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _go(area: str, page: str) -> None:
    st.session_state["pending_navigation_area"] = area
    st.session_state["pending_navigation_page"] = page
    st.rerun()


def _button(label: str, area: str, page: str, key: str, primary: bool = False) -> None:
    if st.button(
        label,
        key=key,
        use_container_width=True,
        type="primary" if primary else "secondary",
    ):
        _go(area, page)


def _daily_tasks() -> list[tuple[str, str, str, str, str]]:
    sales = [
        item for item in _rows("sales_registry")
        if item.get("order_status") not in {"Cancelado", "Cancelada", "Anulado", "Anulada", "Entregado", "Entregada"}
    ]
    plans = {str(item.get("sale_id", "")): item for item in _rows("order_plans")}
    payments = _rows("payment_records")
    purchases = [
        item for item in _rows("purchases_registry")
        if item.get("receipt_status") not in {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    ]
    supplier_payments = _rows("supplier_payment_records")
    inventory = _rows("inventory_registry")
    today = date.today()

    late = 0
    due_today = 0
    without_date = 0
    for sale in sales:
        plan = plans.get(str(sale.get("sale_id", "")), {})
        try:
            due = date.fromisoformat(str(plan.get("delivery_date", "")))
        except ValueError:
            without_date += 1
            continue
        if due < today:
            late += 1
        elif due == today:
            due_today += 1

    receivables = 0.0
    for sale in sales:
        sale_id = str(sale.get("sale_id", ""))
        paid = sum(
            _number(item.get("amount"))
            for item in payments
            if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
        )
        receivables += max(_number(sale.get("total")) - paid, 0.0)

    payables = 0.0
    for purchase in purchases:
        purchase_id = str(purchase.get("purchase_id", ""))
        paid = sum(
            _number(item.get("amount"))
            for item in supplier_payments
            if str(item.get("purchase_id", "")) == purchase_id and not item.get("reversed")
        )
        payables += max(_number(purchase.get("total")) - paid, 0.0)

    low_stock = sum(
        1
        for item in inventory
        if _number(item.get("minimum_stock", item.get("reorder_point", 0.0))) > 0
        and _number(item.get("available_quantity", item.get("quantity", 0.0)))
        <= _number(item.get("minimum_stock", item.get("reorder_point", 0.0)))
    )

    tasks: list[tuple[str, str, str, str, str]] = []
    if late:
        tasks.append(("Urgente", "Resolver pedidos atrasados", f"{late} pedido(s) fuera de fecha.", "Ventas y clientes", "Agenda de producción y entregas"))
    if due_today:
        tasks.append(("Hoy", "Preparar entregas", f"{due_today} entrega(s) programada(s) para hoy.", "Ventas y clientes", "Agenda de producción y entregas"))
    if receivables > 0:
        tasks.append(("Hoy", "Dar seguimiento a cobros", f"Pendiente: {format_money(receivables)}.", "Ventas y clientes", "Cuentas por cobrar"))
    if low_stock:
        tasks.append(("Urgente", "Reponer inventario", f"{low_stock} material(es) en nivel crítico.", "Productos e inventario", "Alertas de inventario"))
    if payables > 0:
        tasks.append(("Planificar", "Revisar pagos a proveedores", f"Pendiente: {format_money(payables)}.", "Compras y proveedores", "Cuentas por pagar"))
    if without_date:
        tasks.append(("Planificar", "Asignar fechas de entrega", f"{without_date} pedido(s) sin fecha.", "Ventas y clientes", "Agenda de producción y entregas"))
    return tasks


def _render_today() -> None:
    st.markdown("### Qué hacer hoy")
    tasks = _daily_tasks()
    if not tasks:
        st.success("No hay tareas críticas generadas automáticamente para hoy.")
    for index, (priority, title, detail, area, page) in enumerate(tasks):
        with st.container(border=True):
            columns = st.columns([1, 3, 1])
            columns[0].metric("Prioridad", priority)
            with columns[1]:
                st.markdown(f"#### {title}")
                st.caption(detail)
            with columns[2]:
                _button("Resolver", area, page, f"daily_task_{index}", priority == "Urgente")


def _render_quick_create() -> None:
    st.markdown("### Crear rápidamente")
    actions = (
        ("Nuevo cliente", "Ventas y clientes", "Clientes"),
        ("Nueva venta", "Ventas y clientes", "Ventas y pedidos"),
        ("Registrar cobro", "Ventas y clientes", "Cuentas por cobrar"),
        ("Registrar gasto", "Administración", "Gastos y presupuesto"),
        ("Nueva compra", "Compras y proveedores", "Compras"),
        ("Ajustar inventario", "Productos e inventario", "Ajustes de inventario"),
    )
    columns = st.columns(3)
    for index, (label, area, page) in enumerate(actions):
        with columns[index % 3]:
            _button(label, area, page, f"quick_action_{index}", index in {1, 2})


def render_control_center_today() -> None:
    render_page_header(
        "Centro de control",
        "Tu plan de trabajo diario, prioridades y accesos para actuar sin perder tiempo.",
    )
    _render_today()
    _render_quick_create()
    st.divider()

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_control_center()
    finally:
        base.render_page_header = original_header

    render_info_card(
        "Plan diario automático",
        "Las tareas se recalculan con pedidos, cobros, pagos e inventario de la sesión actual.",
        "QUÉ HACER HOY",
    )
