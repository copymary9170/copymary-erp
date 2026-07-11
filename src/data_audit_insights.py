"""Resumen ejecutivo, filtros y exportación para la auditoría de datos."""

from collections import Counter
from datetime import datetime
import csv
import io

import streamlit as st

from src import data_audit as base
from src.components import render_page_header
from src.session_utils import read_list as _rows


def _number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _duplicates(items: list[dict], key: str) -> list[str]:
    values = [str(item.get(key, "")) for item in items if item.get(key)]
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _issue(severity: str, category: str, message: str, area: str) -> dict:
    return {"severity": severity, "category": category, "message": message, "area": area}


def _executive_findings() -> tuple[list[dict], dict[str, int]]:
    clients = _rows("customers_registry")
    sales = _rows("sales_registry")
    suppliers = _rows("suppliers_registry")
    purchases = _rows("purchases_registry")
    inventory = _rows("inventory_registry")
    products = _rows("products_registry")
    payments = _rows("payment_records")
    supplier_payments = _rows("supplier_payment_records")
    members = _rows("team_members")
    assignments = _rows("commission_assignments")

    findings: list[dict] = []
    sources = (
        (clients, "client_id", "Clientes", "Ventas"),
        (sales, "sale_id", "Ventas", "Ventas"),
        (suppliers, "supplier_id", "Proveedores", "Compras"),
        (purchases, "purchase_id", "Compras", "Compras"),
        (inventory, "item_id", "Inventario", "Inventario"),
        (products, "product_id", "Productos", "Producción"),
        (members, "member_id", "Equipo", "Administración"),
    )
    for records, key, label, area in sources:
        duplicated = _duplicates(records, key)
        if duplicated:
            findings.append(_issue("Crítica", "ID duplicado", f"{label}: {', '.join(duplicated)}", area))

    client_ids = {str(item.get("client_id", "")) for item in clients}
    supplier_ids = {str(item.get("supplier_id", "")) for item in suppliers}
    sale_ids = {str(item.get("sale_id", "")) for item in sales}
    purchase_ids = {str(item.get("purchase_id", "")) for item in purchases}
    inventory_ids = {str(item.get("item_id", "")) for item in inventory}
    member_ids = {str(item.get("member_id", "")) for item in members}

    for sale in sales:
        client_id = str(sale.get("client_id", ""))
        if client_id and client_id not in client_ids:
            findings.append(_issue("Alta", "Referencia rota", f"Venta {sale.get('sale_id', '')} sin cliente válido", "Ventas"))
    for purchase in purchases:
        supplier_id = str(purchase.get("supplier_id", ""))
        item_id = str(purchase.get("inventory_item_id", ""))
        if supplier_id and supplier_id not in supplier_ids:
            findings.append(_issue("Alta", "Referencia rota", f"Compra {purchase.get('purchase_id', '')} sin proveedor válido", "Compras"))
        if item_id and item_id not in inventory_ids:
            findings.append(_issue("Alta", "Referencia rota", f"Compra {purchase.get('purchase_id', '')} sin material válido", "Inventario"))
    for item in inventory:
        if _number(item.get("available_quantity", item.get("quantity", 0.0))) < 0:
            findings.append(_issue("Crítica", "Inventario negativo", str(item.get("name", "Material")), "Inventario"))
    for product in products:
        missing = [
            str(component.get("item_id", ""))
            for component in product.get("recipe", [])
            if isinstance(component, dict)
            and str(component.get("item_id", ""))
            and str(component.get("item_id", "")) not in inventory_ids
        ]
        if missing:
            findings.append(_issue("Alta", "Receta incompleta", f"{product.get('name', 'Producto')}: {', '.join(missing)}", "Producción"))
    for payment in payments:
        if str(payment.get("sale_id", "")) not in sale_ids:
            findings.append(_issue("Alta", "Registro huérfano", f"Cobro {payment.get('payment_id', '')} sin venta", "Ventas"))
    for payment in supplier_payments:
        if str(payment.get("purchase_id", "")) not in purchase_ids:
            findings.append(_issue("Alta", "Registro huérfano", f"Pago {payment.get('payment_id', '')} sin compra", "Compras"))
    for assignment in assignments:
        if str(assignment.get("sale_id", "")) not in sale_ids or str(assignment.get("member_id", "")) not in member_ids:
            findings.append(_issue("Alta", "Comisión huérfana", f"Asignación {assignment.get('assignment_id', '')}", "Administración"))

    coverage = {
        "Ventas": len(clients) + len(sales) + len(payments),
        "Compras": len(suppliers) + len(purchases) + len(supplier_payments),
        "Inventario": len(inventory),
        "Producción": len(products) + len(_rows("production_log")),
        "Administración": len(members) + len(assignments) + len(_rows("cash_movements")),
    }
    return findings, coverage


def _health_score(findings: list[dict], records_checked: int) -> int:
    penalty = sum({"Crítica": 20, "Alta": 10, "Media": 4, "Baja": 1}.get(item["severity"], 2) for item in findings)
    scale = max(records_checked, 10)
    return max(0, min(100, round(100 - (penalty * 10 / scale))))


def _csv_report(findings: list[dict], coverage: dict[str, int], score: int) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Auditoría CopyMary ERP", datetime.now().isoformat(timespec="seconds")])
    writer.writerow(["Puntaje de salud", score])
    writer.writerow([])
    writer.writerow(["Gravedad", "Categoría", "Área", "Hallazgo"])
    for item in findings:
        writer.writerow([item["severity"], item["category"], item["area"], item["message"]])
    writer.writerow([])
    writer.writerow(["Área revisada", "Registros analizados"])
    for area, count in coverage.items():
        writer.writerow([area, count])
    return buffer.getvalue().encode("utf-8-sig")


def render_data_audit_insights() -> None:
    render_page_header(
        "Auditoría de datos",
        "Mide la salud de la información, filtra riesgos y descarga un informe para dar seguimiento.",
    )

    findings, coverage = _executive_findings()
    records_checked = sum(coverage.values())
    score = _health_score(findings, records_checked)
    critical = sum(1 for item in findings if item["severity"] == "Crítica")
    high = sum(1 for item in findings if item["severity"] == "Alta")

    metrics = st.columns(4)
    metrics[0].metric("Salud de los datos", f"{score}/100")
    metrics[1].metric("Registros revisados", str(records_checked))
    metrics[2].metric("Hallazgos críticos", str(critical))
    metrics[3].metric("Hallazgos altos", str(high))

    if score >= 90:
        st.success("La información presenta una salud general alta.")
    elif score >= 70:
        st.warning("La información es utilizable, pero requiere correcciones importantes.")
    else:
        st.error("La integridad de los datos requiere atención prioritaria.")

    st.markdown("### Explorar hallazgos")
    filter_columns = st.columns(2)
    severity_options = ["Todas"] + sorted({item["severity"] for item in findings})
    category_options = ["Todas"] + sorted({item["category"] for item in findings})
    severity = filter_columns[0].selectbox("Gravedad", severity_options, key="audit_insight_severity")
    category = filter_columns[1].selectbox("Categoría", category_options, key="audit_insight_category")
    filtered = [
        item for item in findings
        if (severity == "Todas" or item["severity"] == severity)
        and (category == "Todas" or item["category"] == category)
    ]
    st.caption(f"Mostrando {len(filtered)} de {len(findings)} hallazgo(s).")
    for item in filtered[:20]:
        with st.container(border=True):
            columns = st.columns([1, 2, 2])
            columns[0].metric("Gravedad", item["severity"])
            columns[1].markdown(f"**{item['category']}**")
            columns[1].caption(item["area"])
            columns[2].write(item["message"])

    st.markdown("### Cobertura de la revisión")
    coverage_columns = st.columns(len(coverage))
    for index, (area, count) in enumerate(coverage.items()):
        coverage_columns[index].metric(area, str(count))

    st.download_button(
        "Descargar informe CSV",
        data=_csv_report(findings, coverage, score),
        file_name=f"auditoria_copymary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_data_audit()
    finally:
        base.render_page_header = original_header
