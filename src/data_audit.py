"""Auditoría de consistencia y dependencias para CopyMary ERP."""

import streamlit as st

from src.components import render_info_card, render_page_header


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _duplicates(items: list[dict], key: str) -> list[str]:
    values = [str(item.get(key, "")) for item in items if item.get(key)]
    return sorted({value for value in values if values.count(value) > 1})


def _used_recipe_items(products: list[dict]) -> dict[str, list[str]]:
    usage: dict[str, list[str]] = {}
    for product in products:
        product_name = str(product.get("name", "Producto"))
        for component in product.get("recipe", []):
            if not isinstance(component, dict):
                continue
            item_id = str(component.get("item_id", ""))
            if item_id:
                usage.setdefault(item_id, []).append(product_name)
    return usage


def render_data_audit() -> None:
    with st.container(border=True):
        render_page_header(
            "Auditoría de datos",
            "Detecta duplicados, referencias rotas y registros que no deben eliminarse.",
        )
        st.caption("La auditoría no modifica información; solo indica riesgos y dependencias.")

    clients = _rows("customers_registry")
    sales = _rows("sales_registry")
    suppliers = _rows("suppliers_registry")
    purchases = _rows("purchases_registry")
    inventory = _rows("inventory_registry")
    inventory_movements = _rows("inventory_movements")
    products = _rows("products_registry")
    production_log = _rows("production_log")
    cash = _rows("cash_movements")
    customer_payments = _rows("payment_records")
    supplier_payments = _rows("supplier_payment_records")
    team_payments = _rows("team_payments")
    plans = _rows("order_plans")
    adjustments = _rows("adjustment_records")
    assignments = _rows("commission_assignments")
    members = _rows("team_members")

    issues: list[str] = []
    protections: list[str] = []

    for records, key, label in (
        (clients, "client_id", "Clientes"),
        (sales, "sale_id", "Ventas"),
        (suppliers, "supplier_id", "Proveedores"),
        (purchases, "purchase_id", "Compras"),
        (inventory, "item_id", "Inventario"),
        (products, "product_id", "Catálogo"),
        (production_log, "production_id", "Producción"),
        (cash, "movement_id", "Caja"),
        (adjustments, "adjustment_id", "Ajustes"),
        (members, "member_id", "Equipo"),
    ):
        duplicates = _duplicates(records, key)
        if duplicates:
            issues.append(f"{label} tiene IDs duplicados: {', '.join(duplicates)}")

    client_ids = {str(item.get("client_id", "")) for item in clients}
    supplier_ids = {str(item.get("supplier_id", "")) for item in suppliers}
    sale_ids = {str(item.get("sale_id", "")) for item in sales}
    purchase_ids = {str(item.get("purchase_id", "")) for item in purchases}
    inventory_ids = {str(item.get("item_id", "")) for item in inventory}
    product_ids = {str(item.get("product_id", "")) for item in products}
    member_ids = {str(item.get("member_id", "")) for item in members}

    for sale in sales:
        sale_id = str(sale.get("sale_id", ""))
        client_id = str(sale.get("client_id", ""))
        if client_id and client_id not in client_ids:
            issues.append(f"Venta {sale_id} tiene un cliente inexistente.")
        if any(str(item.get("sale_id", "")) == sale_id for item in customer_payments + plans + assignments):
            protections.append(f"La venta {sale_id} tiene pagos, planificación o comisiones vinculadas y no debe eliminarse.")

    for purchase in purchases:
        purchase_id = str(purchase.get("purchase_id", ""))
        supplier_id = str(purchase.get("supplier_id", ""))
        item_id = str(purchase.get("inventory_item_id", ""))
        if supplier_id and supplier_id not in supplier_ids:
            issues.append(f"Compra {purchase_id} tiene un proveedor inexistente.")
        if item_id and item_id not in inventory_ids:
            issues.append(f"Compra {purchase_id} tiene un material inexistente.")
        if any(str(item.get("purchase_id", "")) == purchase_id for item in supplier_payments):
            protections.append(f"La compra {purchase_id} tiene pagos vinculados y no debe eliminarse.")
        if any(str(item.get("reference", "")) in {purchase_id, f"REV-{purchase_id}"} for item in inventory_movements + cash):
            protections.append(f"La compra {purchase_id} tiene movimientos contables o de inventario y debe conservarse.")

    recipe_usage = _used_recipe_items(products)
    for item in inventory:
        item_id = str(item.get("item_id", ""))
        if float(item.get("available_quantity", 0.0)) < 0:
            issues.append(f"{item.get('name', 'Material')} tiene existencia negativa.")
        if item_id in recipe_usage:
            products_using = ", ".join(sorted(set(recipe_usage[item_id])))
            protections.append(f"El material {item.get('name', item_id)} se usa en recetas: {products_using}.")
        if any(str(movement.get("item_id", "")) == item_id for movement in inventory_movements):
            protections.append(f"El material {item.get('name', item_id)} tiene historial de movimientos y no debe eliminarse.")

    for product in products:
        product_id = str(product.get("product_id", ""))
        missing = [
            str(component.get("item_id", ""))
            for component in product.get("recipe", [])
            if isinstance(component, dict)
            and str(component.get("item_id", ""))
            and str(component.get("item_id", "")) not in inventory_ids
        ]
        if missing:
            issues.append(f"Producto {product.get('name', product_id)} usa materiales inexistentes: {', '.join(missing)}")
        if any(str(record.get("product_id", "")) == product_id for record in production_log):
            protections.append(f"El producto {product.get('name', product_id)} tiene producciones registradas y no debe eliminarse.")

    for production in production_log:
        product_id = str(production.get("product_id", ""))
        if product_id and product_id not in product_ids:
            issues.append(f"Producción {production.get('production_id', '')} referencia un producto inexistente.")
        snapshot = production.get("recipe_snapshot", [])
        if snapshot:
            missing = [
                str(component.get("item_id", ""))
                for component in snapshot
                if isinstance(component, dict)
                and str(component.get("item_id", "")) not in inventory_ids
            ]
            if missing:
                issues.append(f"Producción {production.get('production_id', '')} tiene materiales eliminados en su receta guardada.")

    for payment in customer_payments:
        if str(payment.get("sale_id", "")) not in sale_ids:
            issues.append(f"Abono {payment.get('payment_id', '')} no tiene una venta válida.")
    for payment in supplier_payments:
        if str(payment.get("purchase_id", "")) not in purchase_ids:
            issues.append(f"Pago {payment.get('payment_id', '')} no tiene una compra válida.")
    for payment in team_payments:
        if str(payment.get("member_id", "")) not in member_ids:
            issues.append(f"Pago al equipo {payment.get('payment_id', '')} no tiene un colaborador válido.")
    for plan in plans:
        if str(plan.get("sale_id", "")) not in sale_ids:
            issues.append(f"Plan {plan.get('plan_id', '')} no tiene una venta válida.")
    for assignment in assignments:
        if str(assignment.get("sale_id", "")) not in sale_ids:
            issues.append(f"Asignación {assignment.get('assignment_id', '')} no tiene una venta válida.")
        if str(assignment.get("member_id", "")) not in member_ids:
            issues.append(f"Asignación {assignment.get('assignment_id', '')} no tiene un colaborador válido.")

    metrics = st.columns(4)
    metrics[0].metric("Hallazgos", str(len(issues)))
    metrics[1].metric("Registros protegidos", str(len(set(protections))))
    metrics[2].metric("Productos", str(len(products)))
    metrics[3].metric("Movimientos", str(len(inventory_movements) + len(cash)))

    issue_tab, protection_tab = st.tabs(("Inconsistencias", "Dependencias y protección"))
    with issue_tab:
        if not issues:
            st.success("No se detectaron inconsistencias en los controles disponibles.")
        else:
            for issue in issues:
                st.warning(issue)

    with protection_tab:
        unique_protections = sorted(set(protections))
        if not unique_protections:
            st.info("No se detectaron dependencias que requieran protección especial.")
        else:
            st.warning("Los siguientes registros tienen historial o relaciones activas y no deberían eliminarse:")
            for protection in unique_protections:
                st.write(f"- {protection}")

    render_info_card(
        "Alcance",
        "Revisa IDs, relaciones, recetas, producciones, pagos, movimientos y registros que deben conservarse.",
        "CONTROL DE INTEGRIDAD",
    )
