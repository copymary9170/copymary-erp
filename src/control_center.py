"""Centro de control general para CopyMary ERP."""

from datetime import date, datetime

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import read_list as _records


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _supplier_name(supplier_id: str, suppliers: list[dict]) -> str:
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")) == supplier_id:
            return str(supplier.get("name", "Proveedor"))
    return "Sin proveedor"


def _date_value(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sale_paid(sale: dict, payments: list[dict]) -> float:
    sale_id = str(sale.get("sale_id", ""))
    total = _number(sale.get("total"))
    explicit = sum(
        _number(item.get("amount"))
        for item in payments
        if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
    )
    if explicit > 0:
        return min(explicit, total)
    if sale.get("payment_status") == "Pagado" and sale.get("cash_registered"):
        return total
    return 0.0


def _purchase_paid(purchase: dict, payments: list[dict]) -> float:
    purchase_id = str(purchase.get("purchase_id", ""))
    total = _number(purchase.get("total"))
    explicit = sum(
        _number(item.get("amount"))
        for item in payments
        if str(item.get("purchase_id", "")) == purchase_id and not item.get("reversed")
    )
    if explicit > 0:
        return min(explicit, total)
    if purchase.get("payment_status") == "Pagado" and purchase.get("cash_registered"):
        return total
    return 0.0


def _go(area: str, page: str) -> None:
    st.session_state["pending_navigation_area"] = area
    st.session_state["pending_navigation_page"] = page
    st.rerun()


def _action_button(label: str, area: str, page: str, key: str, primary: bool = False) -> None:
    if st.button(
        label,
        key=key,
        use_container_width=True,
        type="primary" if primary else "secondary",
    ):
        _go(area, page)


def render_control_center() -> None:
    render_page_header(
        "Centro de control",
        "Prioridades, dinero, pedidos e inventario reunidos para decidir qué atender primero.",
    )

    clients = _records("customers_registry")
    sales = _records("sales_registry")
    sale_payments = _records("payment_records")
    plans = _records("order_plans")
    suppliers = _records("suppliers_registry")
    purchases = _records("purchases_registry")
    supplier_payments = _records("supplier_payment_records")
    inventory = _records("inventory_registry")
    cash = _records("cash_movements")

    cancelled = {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    active_sales = [sale for sale in sales if sale.get("order_status") not in cancelled]
    active_purchases = [purchase for purchase in purchases if purchase.get("receipt_status") not in cancelled]

    receivables = sum(
        max(_number(sale.get("total")) - _sale_paid(sale, sale_payments), 0.0)
        for sale in active_sales
    )
    payables = sum(
        max(_number(purchase.get("total")) - _purchase_paid(purchase, supplier_payments), 0.0)
        for purchase in active_purchases
    )
    income = sum(_number(item.get("amount")) for item in cash if item.get("movement_type") == "Ingreso")
    expenses = sum(_number(item.get("amount")) for item in cash if item.get("movement_type") == "Egreso")
    cash_balance = income - expenses

    low_stock = []
    for item in inventory:
        available = _number(item.get("available_quantity", item.get("quantity", 0.0)))
        minimum = _number(item.get("minimum_stock", item.get("reorder_point", 0.0)))
        if minimum > 0 and available <= minimum:
            low_stock.append(item)

    today = date.today()
    plan_map = {str(plan.get("sale_id", "")): plan for plan in plans}
    late_orders: list[tuple[dict, dict]] = []
    today_orders: list[tuple[dict, dict]] = []
    unplanned_orders: list[dict] = []

    for sale in active_sales:
        if sale.get("order_status") in {"Entregado", "Entregada"}:
            continue
        plan = plan_map.get(str(sale.get("sale_id", "")), {})
        due = _date_value(str(plan.get("delivery_date", "")))
        if due is None:
            unplanned_orders.append(sale)
        elif due < today:
            late_orders.append((sale, plan))
        elif due == today:
            today_orders.append((sale, plan))

    critical_count = len(late_orders) + len(low_stock)
    warning_count = len(today_orders) + len(unplanned_orders)

    st.markdown("### Resumen del negocio")
    first = st.columns(4)
    first[0].metric("Caja disponible", format_money(cash_balance))
    first[1].metric("Por cobrar", format_money(receivables))
    first[2].metric("Por pagar", format_money(payables))
    first[3].metric("Prioridades críticas", str(critical_count))

    second = st.columns(4)
    second[0].metric("Pedidos activos", str(len(active_sales)))
    second[1].metric("Entregas hoy", str(len(today_orders)))
    second[2].metric("Inventario bajo", str(len(low_stock)))
    second[3].metric("Alertas preventivas", str(warning_count))

    if critical_count:
        st.error(f"Hay {critical_count} prioridad(es) crítica(s) que requieren atención inmediata.")
    elif warning_count:
        st.warning(f"Hay {warning_count} pendiente(s) preventivo(s) para revisar hoy.")
    else:
        st.success("La operación no presenta alertas críticas en este momento.")

    st.markdown("### Acciones recomendadas")
    action_columns = st.columns(4)
    with action_columns[0]:
        render_info_card(
            "Pedidos atrasados",
            f"{len(late_orders)} pedido(s) fuera de fecha.",
            "PRIORIDAD ALTA" if late_orders else "AL DÍA",
        )
        _action_button("Abrir agenda", "Ventas y clientes", "Agenda de producción y entregas", "control_agenda", bool(late_orders))
    with action_columns[1]:
        render_info_card(
            "Cobros pendientes",
            f"Saldo pendiente: {format_money(receivables)}.",
            "SEGUIMIENTO" if receivables else "AL DÍA",
        )
        _action_button("Abrir cuentas por cobrar", "Ventas y clientes", "Cuentas por cobrar", "control_receivables")
    with action_columns[2]:
        render_info_card(
            "Inventario crítico",
            f"{len(low_stock)} material(es) en mínimo o agotados.",
            "PRIORIDAD ALTA" if low_stock else "AL DÍA",
        )
        _action_button("Abrir alertas", "Productos e inventario", "Alertas de inventario", "control_inventory", bool(low_stock))
    with action_columns[3]:
        render_info_card(
            "Pagos a proveedores",
            f"Saldo pendiente: {format_money(payables)}.",
            "SEGUIMIENTO" if payables else "AL DÍA",
        )
        _action_button("Abrir cuentas por pagar", "Compras y proveedores", "Cuentas por pagar", "control_payables")

    st.markdown("### Pedidos que requieren atención")
    attention_orders = late_orders + today_orders
    if not attention_orders:
        st.info("No hay pedidos atrasados ni entregas programadas para hoy.")
    for sale, plan in attention_orders[:8]:
        due = _date_value(str(plan.get("delivery_date", "")))
        is_late = bool(due and due < today)
        with st.container(border=True):
            columns = st.columns([3, 1, 1, 1])
            with columns[0]:
                st.markdown(f"#### {sale.get('description', 'Pedido')}")
                st.caption(
                    f"{_client_name(str(sale.get('client_id', '')), clients)} · "
                    f"Entrega {plan.get('delivery_date', 'Sin fecha')}"
                )
            columns[1].metric("Estado", "Atrasado" if is_late else "Hoy")
            columns[2].metric("Prioridad", str(plan.get("priority", "Normal")))
            columns[3].metric("Avance", f"{int(_number(plan.get('progress')))}%")

    if unplanned_orders:
        with st.expander(f"Pedidos sin fecha: {len(unplanned_orders)}", expanded=False):
            for sale in unplanned_orders[:10]:
                st.write(f"• {sale.get('description', 'Pedido')} · {_client_name(str(sale.get('client_id', '')), clients)}")

    st.markdown("### Inventario crítico")
    if not low_stock:
        st.success("No hay materiales en mínimo o agotados.")
    else:
        for item in low_stock[:8]:
            available = _number(item.get("available_quantity", item.get("quantity", 0.0)))
            minimum = _number(item.get("minimum_stock", item.get("reorder_point", 0.0)))
            with st.container(border=True):
                columns = st.columns([2, 1, 1, 1])
                columns[0].metric("Material", str(item.get("name", "Material")))
                columns[1].metric("Disponible", f"{available:,.2f}")
                columns[2].metric("Mínimo", f"{minimum:,.2f}")
                columns[3].metric("Faltante", f"{max(minimum - available, 0.0):,.2f}")

    st.markdown("### Mayores compromisos")
    rows = st.columns(2)
    with rows[0]:
        st.markdown("#### Clientes con saldo")
        customer_balances: list[tuple[str, float]] = []
        for sale in active_sales:
            balance = max(_number(sale.get("total")) - _sale_paid(sale, sale_payments), 0.0)
            if balance > 0:
                customer_balances.append((_client_name(str(sale.get("client_id", "")), clients), balance))
        for name, balance in sorted(customer_balances, key=lambda item: item[1], reverse=True)[:5]:
            st.write(f"**{name}** · {format_money(balance)}")
        if not customer_balances:
            st.caption("Sin cuentas pendientes de clientes.")

    with rows[1]:
        st.markdown("#### Proveedores con saldo")
        supplier_balances: list[tuple[str, float]] = []
        for purchase in active_purchases:
            balance = max(_number(purchase.get("total")) - _purchase_paid(purchase, supplier_payments), 0.0)
            if balance > 0:
                supplier_balances.append((_supplier_name(str(purchase.get("supplier_id", "")), suppliers), balance))
        for name, balance in sorted(supplier_balances, key=lambda item: item[1], reverse=True)[:5]:
            st.write(f"**{name}** · {format_money(balance)}")
        if not supplier_balances:
            st.caption("Sin cuentas pendientes de proveedores.")

    render_info_card(
        "Actualización del panel",
        f"Datos calculados con la sesión actual a las {datetime.now().strftime('%H:%M:%S')}.",
        "CENTRO DE CONTROL",
    )
