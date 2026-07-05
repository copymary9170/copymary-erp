"""Auditoría básica de consistencia para CopyMary ERP."""

import streamlit as st

from src.components import render_info_card, render_page_header


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _duplicates(items: list[dict], key: str) -> list[str]:
    values = [str(item.get(key, "")) for item in items if item.get(key)]
    return sorted({value for value in values if values.count(value) > 1})


def render_data_audit() -> None:
    with st.container(border=True):
        render_page_header("Auditoría de datos", "Detecta duplicados y referencias rotas entre módulos.")
        st.caption("La auditoría no modifica información.")

    clients = _rows("customers_registry")
    sales = _rows("sales_registry")
    suppliers = _rows("suppliers_registry")
    purchases = _rows("purchases_registry")
    inventory = _rows("inventory_registry")
    cash = _rows("cash_movements")
    customer_payments = _rows("payment_records")
    supplier_payments = _rows("supplier_payment_records")
    plans = _rows("order_plans")
    adjustments = _rows("adjustment_records")

    issues: list[str] = []
    for records, key, label in (
        (clients, "client_id", "Clientes"),
        (sales, "sale_id", "Ventas"),
        (suppliers, "supplier_id", "Proveedores"),
        (purchases, "purchase_id", "Compras"),
        (inventory, "item_id", "Inventario"),
        (cash, "movement_id", "Caja"),
        (adjustments, "adjustment_id", "Ajustes"),
    ):
        duplicates = _duplicates(records, key)
        if duplicates:
            issues.append(f"{label} tiene IDs duplicados: {', '.join(duplicates)}")

    client_ids = {str(item.get("client_id", "")) for item in clients}
    supplier_ids = {str(item.get("supplier_id", "")) for item in suppliers}
    sale_ids = {str(item.get("sale_id", "")) for item in sales}
    purchase_ids = {str(item.get("purchase_id", "")) for item in purchases}
    inventory_ids = {str(item.get("item_id", "")) for item in inventory}

    for sale in sales:
        client_id = str(sale.get("client_id", ""))
        if client_id and client_id not in client_ids:
            issues.append(f"Venta {sale.get('sale_id', '')} tiene un cliente inexistente.")
    for purchase in purchases:
        supplier_id = str(purchase.get("supplier_id", ""))
        item_id = str(purchase.get("inventory_item_id", ""))
        if supplier_id and supplier_id not in supplier_ids:
            issues.append(f"Compra {purchase.get('purchase_id', '')} tiene un proveedor inexistente.")
        if item_id and item_id not in inventory_ids:
            issues.append(f"Compra {purchase.get('purchase_id', '')} tiene un material inexistente.")
    for payment in customer_payments:
        if str(payment.get("sale_id", "")) not in sale_ids:
            issues.append(f"Abono {payment.get('payment_id', '')} no tiene una venta válida.")
    for payment in supplier_payments:
        if str(payment.get("purchase_id", "")) not in purchase_ids:
            issues.append(f"Pago {payment.get('payment_id', '')} no tiene una compra válida.")
    for plan in plans:
        if str(plan.get("sale_id", "")) not in sale_ids:
            issues.append(f"Plan {plan.get('plan_id', '')} no tiene una venta válida.")
    for item in inventory:
        if float(item.get("available_quantity", 0.0)) < 0:
            issues.append(f"{item.get('name', 'Material')} tiene existencia negativa.")

    metrics = st.columns(4)
    metrics[0].metric("Hallazgos", str(len(issues)))
    metrics[1].metric("Ventas", str(len(sales)))
    metrics[2].metric("Compras", str(len(purchases)))
    metrics[3].metric("Movimientos de caja", str(len(cash)))

    if not issues:
        st.success("No se detectaron inconsistencias en los controles disponibles.")
    else:
        for issue in issues:
            st.warning(issue)

    render_info_card("Alcance", "Revisa IDs, relaciones básicas y existencias negativas.", "CONTROL DE INTEGRIDAD")
