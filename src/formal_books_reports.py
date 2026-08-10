"""Libros operativos de solo lectura para el centro de Reportes.

No pretende sustituir libros fiscales oficiales ni asesoría tributaria. Consolida
los registros existentes del ERP para control interno y exportación.
"""
from __future__ import annotations

import csv
from io import StringIO

import streamlit as st

from src.session_utils import read_list


def _rows(key: str) -> list[dict]:
    return [dict(row) for row in read_list(key) if isinstance(row, dict)]


def _num(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _csv(headers: list[str], rows: list[list[object]]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _sale_purchase_book() -> None:
    sales = _rows("sales_registry")
    purchases = _rows("purchases_registry")
    customers = {str(row.get("client_id", "")): str(row.get("name", "")) for row in _rows("customers_registry")}
    suppliers = {str(row.get("supplier_id", "")): str(row.get("name", "")) for row in _rows("suppliers_registry")}

    book: list[dict] = []
    for row in sales:
        if str(row.get("order_status", "")).casefold() in {"cancelado", "cancelada", "anulado", "anulada"}:
            continue
        book.append({
            "Fecha": str(row.get("created_at_utc", ""))[:10],
            "Tipo": "Venta",
            "Documento": str(row.get("sale_id", "")),
            "Tercero": customers.get(str(row.get("client_id", "")), "Venta sin cliente"),
            "Concepto": str(row.get("description", "")),
            "Base": _num(row.get("subtotal", row.get("total", 0.0))),
            "IVA": _num(row.get("iva_amount")),
            "IGTF": _num(row.get("igtf_amount")),
            "Total": _num(row.get("total")),
            "Estado": str(row.get("payment_status", "")),
        })
    for row in purchases:
        if str(row.get("receipt_status", "")).casefold() in {"cancelada", "cancelado", "anulada", "anulado"}:
            continue
        total = _num(row.get("total"))
        book.append({
            "Fecha": str(row.get("created_at_utc", ""))[:10],
            "Tipo": "Compra",
            "Documento": str(row.get("purchase_id", "")),
            "Tercero": suppliers.get(str(row.get("supplier_id", "")), "Sin proveedor"),
            "Concepto": str(row.get("material_name", "")),
            "Base": total,
            "IVA": _num(row.get("iva_amount")),
            "IGTF": 0.0,
            "Total": total + _num(row.get("iva_amount")) if row.get("total_excludes_tax") else total,
            "Estado": str(row.get("payment_status", row.get("receipt_status", ""))),
        })
    book.sort(key=lambda row: (row["Fecha"], row["Tipo"], row["Documento"]), reverse=True)

    metrics = st.columns(3)
    metrics[0].metric("Ventas", str(sum(1 for row in book if row["Tipo"] == "Venta")))
    metrics[1].metric("Compras", str(sum(1 for row in book if row["Tipo"] == "Compra")))
    metrics[2].metric("Registros", str(len(book)))
    if not book:
        st.info("Todavía no hay ventas o compras para consolidar.")
        return
    st.dataframe(book, use_container_width=True, hide_index=True)
    headers = list(book[0])
    st.download_button(
        "Descargar libro de ventas y compras",
        _csv(headers, [[row[key] for key in headers] for row in book]),
        file_name="copymary_libro_ventas_compras.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _inventory_book() -> None:
    movements = _rows("inventory_movements")
    adjustments = _rows("adjustment_records")
    rows: list[dict] = []
    for row in movements:
        rows.append({
            "Fecha": str(row.get("created_at_utc", ""))[:19],
            "Tipo": str(row.get("movement_type", "Movimiento")),
            "Material": str(row.get("item_name", "")),
            "Cantidad": _num(row.get("quantity")),
            "Unidad": str(row.get("unit_name", "unidad")),
            "Motivo": str(row.get("reason", "")),
            "Anterior": _num(row.get("previous_quantity")),
            "Resultante": _num(row.get("resulting_quantity")),
            "Referencia": str(row.get("movement_id", "")),
        })
    for row in adjustments:
        if not row.get("inventory_reversed"):
            continue
        rows.append({
            "Fecha": str(row.get("created_at_utc", ""))[:19],
            "Tipo": "Ajuste / reverso",
            "Material": str(row.get("description", "")),
            "Cantidad": 0.0,
            "Unidad": "—",
            "Motivo": str(row.get("reason", "")),
            "Anterior": 0.0,
            "Resultante": 0.0,
            "Referencia": str(row.get("reference_id", "")),
        })
    rows.sort(key=lambda row: row["Fecha"], reverse=True)

    if not rows:
        st.info("Todavía no hay entradas, salidas o ajustes para mostrar.")
        return
    st.dataframe(rows, use_container_width=True, hide_index=True)
    headers = list(rows[0])
    st.download_button(
        "Descargar libro de entradas, salidas y ajustes",
        _csv(headers, [[row[key] for key in headers] for row in rows]),
        file_name="copymary_libro_inventario.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _control_checklist() -> None:
    checks = [
        ("Ventas", bool(_rows("sales_registry")), "Hay ventas registradas para el período de trabajo."),
        ("Compras", bool(_rows("purchases_registry")), "Hay compras registradas para el período de trabajo."),
        ("Caja", bool(_rows("cash_movements")), "Hay movimientos de caja disponibles para conciliación."),
        ("Inventario", bool(_rows("inventory_registry")), "Existe inventario registrado."),
        ("Movimientos de inventario", bool(_rows("inventory_movements")), "Existe trazabilidad de entradas y salidas."),
        ("Respaldos", bool(st.session_state.get("last_backup_at")), "Se detectó una referencia de respaldo en la sesión."),
    ]
    st.warning("Lista de control interno. No certifica cumplimiento fiscal ni sustituye revisión contable o tributaria.")
    st.dataframe(
        [{"Control": name, "Estado": "Disponible" if ok else "Pendiente", "Detalle": detail} for name, ok, detail in checks],
        use_container_width=True,
        hide_index=True,
    )


def render_formal_books() -> None:
    st.markdown("#### Libros y controles operativos")
    st.caption("Consolida automáticamente la información ya registrada; no requiere volver a cargar ventas, compras o movimientos.")
    sales_tab, inventory_tab, checklist_tab = st.tabs((
        "Ventas y compras", "Entradas, salidas y ajustes", "Lista de control"
    ))
    with sales_tab:
        _sale_purchase_book()
    with inventory_tab:
        _inventory_book()
    with checklist_tab:
        _control_checklist()
