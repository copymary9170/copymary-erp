"""Centro de control general para CopyMary ERP."""

from datetime import date, datetime

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _records(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


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


def _sale_paid(sale: dict, payments: list[dict]) -> float:
    sale_id = str(sale.get("sale_id", ""))
    total = float(sale.get("total", 0.0))
    explicit = sum(float(item.get("amount", 0.0)) for item in payments if str(item.get("sale_id", "")) == sale_id)
    if explicit > 0:
        return min(explicit, total)
    if sale.get("payment_status") == "Pagado" and sale.get("cash_registered"):
        return total
    return 0.0


def _purchase_paid(purchase: dict, payments: list[dict]) -> float:
    purchase_id = str(purchase.get("purchase_id", ""))
    total = float(purchase.get("total", 0.0))
    explicit = sum(float(item.get("amount", 0.0)) for item in payments if str(item.get("purchase_id", "")) == purchase_id)
    if explicit > 0:
        return min(explicit, total)
    if purchase.get("payment_status") == "Pagado" and purchase.get("cash_registered"):
        return total
    return 0.0


def render_control_center() -> None:
    with st.container(border=True):
        render_page_header(
            "Centro de control",
            "Vista general del negocio con alertas operativas, financieras y de inventario.",
        )
        st.caption("Todos los indicadores corresponden a la sesión actual.")

    clients = _records("customers_registry")
    sales = _records("sales_registry")
    sale_payments = _records("payment_records")
    plans = _records("order_plans")
    suppliers = _records("suppliers_registry")
    purchases = _records("purchases_registry")
    supplier_payments = _records("supplier_payment_records")
    inventory = _records("inventory_registry")
    cash = _records("cash_movements")

    active_sales = [sale for sale in sales if sale.get("order_status") != "Cancelado"]
    active_purchases = [purchase for purchase in purchases if purchase.get("receipt_status") != "Cancelada"]

    receivables = sum(
        max(float(sale.get("total", 0.0)) - _sale_paid(sale, sale_payments), 0.0)
        for sale in active_sales
    )
    payables = sum(
        max(float(purchase.get("total", 0.0)) - _purchase_paid(purchase, supplier_payments), 0.0)
        for purchase in active_purchases
    )
    income = sum(float(item.get("amount", 0.0)) for item in cash if item.get("movement_type") == "Ingreso")
    expenses = sum(float(item.get("amount", 0.0)) for item in cash if item.get("movement_type") == "Egreso")
    low_stock = [
        item
        for item in inventory
        if float(item.get("available_quantity", 0.0)) <= float(item.get("minimum_stock", 0.0))
    ]

    first = st.columns(4)
    first[0].metric("Clientes", str(len(clients)))
    first[1].metric("Ventas activas", str(len(active_sales)))
    first[2].metric("Por cobrar", format_money(receivables))
    first[3].metric("Por pagar", format_money(payables))

    second = st.columns(4)
    second[0].metric("Saldo de caja", format_money(income - expenses))
    second[1].metric("Compras activas", str(len(active_purchases)))
    second[2].metric("Materiales bajos", str(len(low_stock)))
    second[3].metric("Proveedores", str(len(suppliers)))

    today = date.today()
    plan_map = {str(plan.get("sale_id", "")): plan for plan in plans}
    late_orders: list[tuple[dict, dict]] = []
    today_orders: list[tuple[dict, dict]] = []
    unplanned_orders: list[dict] = []

    for sale in active_sales:
        if sale.get("order_status") == "Entregado":
            continue
        plan = plan_map.get(str(sale.get("sale_id", "")), {})
        due = _date_value(str(plan.get("delivery_date", "")))
        if due is None:
            unplanned_orders.append(sale)
        elif due < today:
            late_orders.append((sale, plan))
        elif due == today:
            today_orders.append((sale, plan))

    st.divider()
    st.subheader("Alertas prioritarias")
    alerts = st.columns(4)
    alerts[0].metric("Pedidos atrasados", str(len(late_orders)))
    alerts[1].metric("Entregas hoy", str(len(today_orders)))
    alerts[2].metric("Sin fecha", str(len(unplanned_orders)))
    alerts[3].metric("Inventario crítico", str(len(low_stock)))

    if late_orders:
        st.error(f"Hay {len(late_orders)} pedido(s) atrasado(s) que requieren atención.")
    if receivables > 0:
        st.warning(f"Hay {format_money(receivables)} pendiente por cobrar.")
    if payables > 0:
        st.warning(f"Hay {format_money(payables)} pendiente por pagar a proveedores.")
    if not late_orders and receivables <= 0 and payables <= 0 and not low_stock:
        st.success("No hay alertas críticas en este momento.")

    st.subheader("Pedidos que requieren atención")
    attention_orders = late_orders + today_orders
    if not attention_orders:
        st.info("No hay pedidos atrasados ni entregas programadas para hoy.")
    else:
        for sale, plan in attention_orders[:8]:
            with st.container(border=True):
                columns = st.columns([3, 1, 1])
                with columns[0]:
                    st.markdown(f"### {sale.get('description', 'Pedido')}")
                    st.caption(
                        f"{_client_name(str(sale.get('client_id', '')), clients)} · "
                        f"Entrega {plan.get('delivery_date', 'Sin fecha')}"
                    )
                columns[1].metric("Prioridad", str(plan.get("priority", "Normal")))
                columns[2].metric("Avance", f"{int(plan.get('progress', 0))}%")

    st.subheader("Inventario crítico")
    if not low_stock:
        st.success("No hay materiales en mínimo o agotados.")
    else:
        for item in low_stock[:8]:
            with st.container(border=True):
                columns = st.columns(3)
                columns[0].metric("Material", str(item.get("name", "Material")))
                columns[1].metric(
                    "Disponible",
                    f"{float(item.get('available_quantity', 0.0)):,.2f} {item.get('unit_name', 'unidad')}",
                )
                columns[2].metric(
                    "Mínimo",
                    f"{float(item.get('minimum_stock', 0.0)):,.2f}",
                )

    st.subheader("Mayores compromisos")
    rows = st.columns(2)
    with rows[0]:
        st.markdown("#### Clientes con saldo")
        customer_balances: list[tuple[str, float]] = []
        for sale in active_sales:
            balance = max(float(sale.get("total", 0.0)) - _sale_paid(sale, sale_payments), 0.0)
            if balance > 0:
                customer_balances.append((_client_name(str(sale.get("client_id", "")), clients), balance))
        for name, balance in sorted(customer_balances, key=lambda item: item[1], reverse=True)[:5]:
            st.write(f"{name}: {format_money(balance)}")
        if not customer_balances:
            st.caption("Sin cuentas pendientes de clientes.")

    with rows[1]:
        st.markdown("#### Proveedores con saldo")
        supplier_balances: list[tuple[str, float]] = []
        for purchase in active_purchases:
            balance = max(float(purchase.get("total", 0.0)) - _purchase_paid(purchase, supplier_payments), 0.0)
            if balance > 0:
                supplier_balances.append((_supplier_name(str(purchase.get("supplier_id", "")), suppliers), balance))
        for name, balance in sorted(supplier_balances, key=lambda item: item[1], reverse=True)[:5]:
            st.write(f"{name}: {format_money(balance)}")
        if not supplier_balances:
            st.caption("Sin cuentas pendientes de proveedores.")

    render_info_card(
        "Estado general",
        f"Actualizado en la sesión a las {datetime.now().strftime('%H:%M:%S')}.",
        "CENTRO DE CONTROL",
    )
