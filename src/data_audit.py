"""Auditoría de consistencia y dependencias para CopyMary ERP."""

from collections import Counter

import streamlit as st

from src.components import render_info_card, render_page_header
from src.session_utils import read_list as _rows


def _duplicates(items: list[dict], key: str) -> list[str]:
    values = [str(item.get(key, "")) for item in items if item.get(key)]
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _go(area: str, page: str) -> None:
    st.session_state["pending_navigation_area"] = area
    st.session_state["pending_navigation_page"] = page
    st.rerun()


def _finding(
    severity: str,
    category: str,
    message: str,
    impact: str,
    area: str,
    page: str,
) -> dict:
    return {
        "severity": severity,
        "category": category,
        "message": message,
        "impact": impact,
        "area": area,
        "page": page,
    }


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
    render_page_header(
        "Auditoría de datos",
        "Revisa la integridad del ERP, prioriza riesgos y abre directamente el módulo donde debes corregirlos.",
    )
    st.caption("La auditoría analiza la sesión actual y no modifica información automáticamente.")

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

    findings: list[dict] = []
    protections: list[str] = []

    duplicate_sources = (
        (clients, "client_id", "Clientes", "Ventas y clientes", "Clientes"),
        (sales, "sale_id", "Ventas", "Ventas y clientes", "Ventas y pedidos"),
        (suppliers, "supplier_id", "Proveedores", "Compras y proveedores", "Proveedores"),
        (purchases, "purchase_id", "Compras", "Compras y proveedores", "Compras"),
        (inventory, "item_id", "Inventario", "Productos e inventario", "Inventario"),
        (products, "product_id", "Catálogo", "Productos e inventario", "Catálogo y producción"),
        (production_log, "production_id", "Producción", "Productos e inventario", "Catálogo y producción"),
        (cash, "movement_id", "Caja", "Administración", "Caja"),
        (adjustments, "adjustment_id", "Ajustes", "Administración", "Anulaciones y ajustes"),
        (members, "member_id", "Equipo", "Administración", "Equipo y comisiones"),
    )
    for records, key, label, area, page in duplicate_sources:
        duplicates = _duplicates(records, key)
        if duplicates:
            findings.append(
                _finding(
                    "Crítica",
                    "ID duplicado",
                    f"{label} tiene IDs duplicados: {', '.join(duplicates)}.",
                    "Puede mezclar historiales, pagos o referencias entre registros distintos.",
                    area,
                    page,
                )
            )

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
            findings.append(_finding("Alta", "Referencia rota", f"Venta {sale_id} tiene un cliente inexistente.", "La venta no puede vincularse correctamente con su cliente.", "Ventas y clientes", "Ventas y pedidos"))
        if any(str(item.get("sale_id", "")) == sale_id for item in customer_payments + plans + assignments):
            protections.append(f"Venta {sale_id}: tiene pagos, planificación o comisiones vinculadas.")

    for purchase in purchases:
        purchase_id = str(purchase.get("purchase_id", ""))
        supplier_id = str(purchase.get("supplier_id", ""))
        item_id = str(purchase.get("inventory_item_id", ""))
        if supplier_id and supplier_id not in supplier_ids:
            findings.append(_finding("Alta", "Referencia rota", f"Compra {purchase_id} tiene un proveedor inexistente.", "La deuda y el historial de compra quedan sin responsable válido.", "Compras y proveedores", "Compras"))
        if item_id and item_id not in inventory_ids:
            findings.append(_finding("Alta", "Referencia rota", f"Compra {purchase_id} tiene un material inexistente.", "El inventario no puede reconciliar correctamente la entrada.", "Compras y proveedores", "Compras"))
        if any(str(item.get("purchase_id", "")) == purchase_id for item in supplier_payments):
            protections.append(f"Compra {purchase_id}: tiene pagos vinculados.")
        if any(str(item.get("reference", "")) in {purchase_id, f"REV-{purchase_id}"} for item in inventory_movements + cash):
            protections.append(f"Compra {purchase_id}: tiene movimientos contables o de inventario.")

    recipe_usage = _used_recipe_items(products)
    for item in inventory:
        item_id = str(item.get("item_id", ""))
        if _number(item.get("available_quantity")) < 0:
            findings.append(_finding("Crítica", "Inventario negativo", f"{item.get('name', 'Material')} tiene existencia negativa.", "Puede causar costos, producción y disponibilidad incorrectos.", "Productos e inventario", "Inventario"))
        if item_id in recipe_usage:
            protections.append(f"Material {item.get('name', item_id)}: usado en recetas de {', '.join(sorted(set(recipe_usage[item_id])))}.")
        if any(str(movement.get("item_id", "")) == item_id for movement in inventory_movements):
            protections.append(f"Material {item.get('name', item_id)}: tiene historial de movimientos.")

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
            findings.append(_finding("Alta", "Receta incompleta", f"Producto {product.get('name', product_id)} usa materiales inexistentes: {', '.join(missing)}.", "El costo y el consumo de materiales pueden calcularse mal.", "Productos e inventario", "Catálogo y producción"))
        if any(str(record.get("product_id", "")) == product_id for record in production_log):
            protections.append(f"Producto {product.get('name', product_id)}: tiene producciones registradas.")

    for production in production_log:
        product_id = str(production.get("product_id", ""))
        if product_id and product_id not in product_ids:
            findings.append(_finding("Alta", "Referencia rota", f"Producción {production.get('production_id', '')} referencia un producto inexistente.", "La producción queda sin producto válido para costeo e historial.", "Productos e inventario", "Catálogo y producción"))
        snapshot = production.get("recipe_snapshot", [])
        missing = [
            str(component.get("item_id", ""))
            for component in snapshot
            if isinstance(component, dict) and str(component.get("item_id", "")) not in inventory_ids
        ]
        if snapshot and missing:
            findings.append(_finding("Media", "Historial incompleto", f"Producción {production.get('production_id', '')} contiene materiales ya eliminados.", "La receta histórica no puede validarse completamente.", "Productos e inventario", "Catálogo y producción"))

    relation_checks = (
        (customer_payments, "sale_id", sale_ids, "payment_id", "Abono", "Ventas y clientes", "Cuentas por cobrar"),
        (supplier_payments, "purchase_id", purchase_ids, "payment_id", "Pago a proveedor", "Compras y proveedores", "Cuentas por pagar"),
        (team_payments, "member_id", member_ids, "payment_id", "Pago al equipo", "Administración", "Equipo y comisiones"),
        (plans, "sale_id", sale_ids, "plan_id", "Plan", "Ventas y clientes", "Agenda de producción y entregas"),
    )
    for records, foreign_key, valid_ids, display_key, label, area, page in relation_checks:
        for record in records:
            if str(record.get(foreign_key, "")) not in valid_ids:
                findings.append(_finding("Alta", "Registro huérfano", f"{label} {record.get(display_key, '')} no tiene una referencia válida.", "El registro no puede conciliarse con su origen.", area, page))

    for assignment in assignments:
        if str(assignment.get("sale_id", "")) not in sale_ids:
            findings.append(_finding("Alta", "Comisión huérfana", f"Asignación {assignment.get('assignment_id', '')} no tiene una venta válida.", "La comisión puede quedar fuera del cálculo correcto.", "Administración", "Equipo y comisiones"))
        if str(assignment.get("member_id", "")) not in member_ids:
            findings.append(_finding("Alta", "Comisión huérfana", f"Asignación {assignment.get('assignment_id', '')} no tiene un colaborador válido.", "La comisión no puede atribuirse correctamente.", "Administración", "Equipo y comisiones"))

    severity_order = {"Crítica": 0, "Alta": 1, "Media": 2, "Baja": 3}
    findings.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["category"], item["message"]))
    critical = sum(1 for item in findings if item["severity"] == "Crítica")
    high = sum(1 for item in findings if item["severity"] == "Alta")
    medium = sum(1 for item in findings if item["severity"] == "Media")

    metrics = st.columns(4)
    metrics[0].metric("Hallazgos", str(len(findings)))
    metrics[1].metric("Críticos", str(critical))
    metrics[2].metric("Altos", str(high))
    metrics[3].metric("Protegidos", str(len(set(protections))))

    if critical:
        st.error(f"Hay {critical} hallazgo(s) crítico(s) que deben corregirse primero.")
    elif high:
        st.warning(f"Hay {high} hallazgo(s) de prioridad alta.")
    elif findings:
        st.info(f"Hay {medium} hallazgo(s) de prioridad media para revisar.")
    else:
        st.success("No se detectaron inconsistencias en los controles disponibles.")

    issue_tab, summary_tab, protection_tab = st.tabs(("Hallazgos", "Resumen por categoría", "Dependencias protegidas"))

    with issue_tab:
        if not findings:
            st.success("La sesión no presenta inconsistencias detectables.")
        for index, item in enumerate(findings):
            with st.container(border=True):
                columns = st.columns([1, 3, 1])
                columns[0].metric("Gravedad", item["severity"])
                with columns[1]:
                    st.markdown(f"#### {item['category']}")
                    st.write(item["message"])
                    st.caption(f"Impacto: {item['impact']}")
                with columns[2]:
                    if st.button("Corregir", key=f"audit_fix_{index}", use_container_width=True, type="primary" if item["severity"] == "Crítica" else "secondary"):
                        _go(item["area"], item["page"])

    with summary_tab:
        category_counts = Counter(item["category"] for item in findings)
        if not category_counts:
            st.info("No hay categorías con hallazgos.")
        for category, count in category_counts.most_common():
            st.metric(category, str(count))

    with protection_tab:
        unique_protections = sorted(set(protections))
        if not unique_protections:
            st.info("No se detectaron dependencias que requieran protección especial.")
        else:
            st.warning("Estos registros tienen historial o relaciones activas y no deberían eliminarse:")
            for protection in unique_protections:
                st.write(f"- {protection}")

    render_info_card(
        "Alcance de la auditoría",
        "Revisa IDs, relaciones, inventario, recetas, producción, pagos, planificación, comisiones y dependencias que deben conservarse.",
        "CONTROL DE INTEGRIDAD",
    )
