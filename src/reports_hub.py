"""Centro unificado de reportes de CopyMary ERP.

Este módulo es de solo lectura: consume los registros existentes y no crea,
modifica ni elimina transacciones.
"""
from __future__ import annotations

import csv
from io import StringIO

import streamlit as st

from src.components import render_page_header
from src.money import format_money, get_currency
from src.session_utils import read_list


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in read_list(key) if isinstance(item, dict)]


def _csv_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _first(row: dict, *keys: str, default: object = "") -> object:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _date(row: dict) -> str:
    return str(_first(row, "created_at_utc", "expense_date", "date", "movement_date", "received_at_utc"))


def _active_sales(sales: list[dict]) -> list[dict]:
    cancelled = {"cancelado", "cancelada", "anulado", "anulada"}
    return [
        row for row in sales
        if str(row.get("order_status", "")).strip().casefold() not in cancelled
    ]


def _financial_totals() -> dict[str, float]:
    cash = _rows("cash_movements")
    sales = _active_sales(_rows("sales_registry"))
    income = sum(_num(row.get("amount")) for row in cash if row.get("movement_type") == "Ingreso")
    cash_out = sum(_num(row.get("amount")) for row in cash if row.get("movement_type") == "Egreso")
    sales_total = sum(_num(row.get("total")) for row in sales)
    estimated_cost = sum(_num(row.get("estimated_cost")) for row in sales)
    return {
        "income": income,
        "cash_out": cash_out,
        "cash_balance": income - cash_out,
        "sales_total": sales_total,
        "estimated_cost": estimated_cost,
        "estimated_margin": sales_total - estimated_cost,
    }


def _render_documents() -> None:
    sales = _rows("sales_registry")
    quotes = _rows("quotes_registry")
    purchases = _rows("purchases_registry")
    receipts = _rows("receipts_registry") or _rows("goods_receipts")

    metrics = st.columns(4)
    metrics[0].metric("Ventas / pedidos", str(len(sales)))
    metrics[1].metric("Cotizaciones", str(len(quotes)))
    metrics[2].metric("Compras", str(len(purchases)))
    metrics[3].metric("Recepciones", str(len(receipts)))

    document_rows: list[dict] = []
    for label, rows, id_keys, status_keys in (
        ("Venta", sales, ("sale_id", "id"), ("order_status", "status")),
        ("Cotización", quotes, ("quote_id", "id"), ("status",)),
        ("Compra", purchases, ("purchase_id", "id"), ("status", "receipt_status")),
        ("Recepción", receipts, ("receipt_id", "id"), ("status",)),
    ):
        for row in rows:
            document_rows.append({
                "Fecha": _date(row),
                "Tipo": label,
                "Documento": str(_first(row, *id_keys, default="—")),
                "Estado": str(_first(row, *status_keys, default="—")),
                "Monto": _num(_first(row, "total", "amount", "grand_total", default=0.0)),
            })

    document_rows.sort(key=lambda row: row["Fecha"], reverse=True)
    if document_rows:
        st.dataframe(document_rows, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar reporte de documentos",
            _csv_bytes(
                ["Fecha", "Tipo", "Documento", "Estado", "Monto"],
                [[row["Fecha"], row["Tipo"], row["Documento"], row["Estado"], row["Monto"]] for row in document_rows],
            ),
            file_name="copymary_reporte_documentos.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("Todavía no hay documentos para reportar.")


def _render_financial() -> None:
    currency = get_currency()
    totals = _financial_totals()
    expenses = _rows("expense_records")
    paid_sales = [row for row in _active_sales(_rows("sales_registry")) if row.get("payment_status") == "Pagado"]

    first = st.columns(3)
    first[0].metric("Ingresos de caja", format_money(totals["income"], currency))
    first[1].metric("Egresos de caja", format_money(totals["cash_out"], currency))
    first[2].metric("Saldo de caja", format_money(totals["cash_balance"], currency))
    second = st.columns(3)
    second[0].metric("Ventas registradas", format_money(totals["sales_total"], currency))
    second[1].metric("Costo estimado", format_money(totals["estimated_cost"], currency))
    second[2].metric("Margen estimado", format_money(totals["estimated_margin"], currency))

    st.caption(
        "El margen es estimado a partir del costo guardado en las ventas; el saldo de caja usa únicamente movimientos de Caja."
    )
    summary = [
        ["Ingresos de caja", totals["income"]],
        ["Egresos de caja", totals["cash_out"]],
        ["Saldo de caja", totals["cash_balance"]],
        ["Ventas registradas", totals["sales_total"]],
        ["Costo estimado", totals["estimated_cost"]],
        ["Margen estimado", totals["estimated_margin"]],
        ["Ventas pagadas", len(paid_sales)],
        ["Gastos registrados", len(expenses)],
    ]
    st.download_button(
        "Descargar reporte financiero",
        _csv_bytes(["Indicador", "Valor"], summary),
        file_name="copymary_reporte_financiero.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _render_history() -> None:
    events: list[dict] = []
    sources = (
        ("Venta", _rows("sales_registry"), ("sale_id", "id"), ("total", "amount")),
        ("Compra", _rows("purchases_registry"), ("purchase_id", "id"), ("total", "amount")),
        ("Gasto", _rows("expense_records"), ("expense_id", "id"), ("amount",)),
        ("Caja", _rows("cash_movements"), ("movement_id", "id"), ("amount",)),
        ("Inventario", _rows("inventory_movements"), ("movement_id", "id"), ("quantity", "amount")),
    )
    for label, rows, id_keys, value_keys in sources:
        for row in rows:
            events.append({
                "Fecha": _date(row),
                "Origen": label,
                "Referencia": str(_first(row, *id_keys, default="—")),
                "Detalle": str(_first(row, "description", "notes", "category", "movement_type", default="—")),
                "Valor": _num(_first(row, *value_keys, default=0.0)),
            })
    events.sort(key=lambda row: row["Fecha"], reverse=True)
    if not events:
        st.info("Todavía no hay historial para consolidar.")
        return
    st.dataframe(events, use_container_width=True, hide_index=True)
    st.download_button(
        "Descargar histórico consolidado",
        _csv_bytes(
            ["Fecha", "Origen", "Referencia", "Detalle", "Valor"],
            [[row["Fecha"], row["Origen"], row["Referencia"], row["Detalle"], row["Valor"]] for row in events],
        ),
        file_name="copymary_reportes_historicos.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _render_administrative() -> None:
    customers = _rows("customers_registry")
    suppliers = _rows("suppliers_registry")
    inventory = _rows("inventory_registry")
    catalog = _rows("catalog_items")
    receivables = _rows("receivables_registry")
    payables = _rows("payables_registry") or _rows("accounts_payable")

    metrics = st.columns(3)
    metrics[0].metric("Clientes", str(len(customers)))
    metrics[1].metric("Proveedores", str(len(suppliers)))
    metrics[2].metric("Artículos de catálogo", str(len(catalog)))
    metrics2 = st.columns(3)
    metrics2[0].metric("Registros de inventario", str(len(inventory)))
    metrics2[1].metric("Cuentas por cobrar", str(len(receivables)))
    metrics2[2].metric("Cuentas por pagar", str(len(payables)))

    rows = [
        ["Clientes", len(customers)], ["Proveedores", len(suppliers)],
        ["Artículos de catálogo", len(catalog)], ["Registros de inventario", len(inventory)],
        ["Cuentas por cobrar", len(receivables)], ["Cuentas por pagar", len(payables)],
    ]
    st.download_button(
        "Descargar reporte administrativo",
        _csv_bytes(["Indicador", "Cantidad"], rows),
        file_name="copymary_reporte_administrativo.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _render_consolidated() -> None:
    currency = get_currency()
    totals = _financial_totals()
    sales = _active_sales(_rows("sales_registry"))
    purchases = _rows("purchases_registry")
    inventory = _rows("inventory_registry")
    expenses = _rows("expense_records")

    st.info("Copy Mary opera actualmente como una sola empresa. Este reporte consolida todas las áreas del ERP en una vista gerencial.")
    metrics = st.columns(4)
    metrics[0].metric("Ventas", str(len(sales)))
    metrics[1].metric("Compras", str(len(purchases)))
    metrics[2].metric("Gastos", str(len(expenses)))
    metrics[3].metric("Artículos en inventario", str(len(inventory)))
    finance = st.columns(3)
    finance[0].metric("Ingresos", format_money(totals["income"], currency))
    finance[1].metric("Egresos", format_money(totals["cash_out"], currency))
    finance[2].metric("Saldo", format_money(totals["cash_balance"], currency))

    rows = [
        ["Ventas", len(sales)], ["Compras", len(purchases)], ["Gastos", len(expenses)],
        ["Inventario", len(inventory)], ["Ingresos", totals["income"]],
        ["Egresos", totals["cash_out"]], ["Saldo", totals["cash_balance"]],
    ]
    st.download_button(
        "Descargar reporte consolidado",
        _csv_bytes(["Indicador", "Valor"], rows),
        file_name="copymary_reporte_consolidado.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _render_expenses() -> None:
    currency = get_currency()
    expenses = _rows("expense_records")
    cash_out = [row for row in _rows("cash_movements") if row.get("movement_type") == "Egreso"]
    expense_total = sum(_num(row.get("amount")) for row in expenses)
    cash_total = sum(_num(row.get("amount")) for row in cash_out)

    metrics = st.columns(3)
    metrics[0].metric("Gastos registrados", format_money(expense_total, currency))
    metrics[1].metric("Egresos de caja", format_money(cash_total, currency))
    metrics[2].metric("Movimientos de egreso", str(len(cash_out)))

    rows = sorted(expenses, key=_date, reverse=True)
    if rows:
        table = [{
            "Fecha": str(_first(row, "expense_date", "created_at_utc")),
            "Categoría": str(row.get("category", "")),
            "Descripción": str(row.get("description", "")),
            "Método": str(row.get("payment_method", "")),
            "Monto": _num(row.get("amount")),
            "Origen": str(row.get("source", "")),
        } for row in rows]
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar reporte de egresos",
            _csv_bytes(
                ["Fecha", "Categoría", "Descripción", "Método", "Monto", "Origen"],
                [[r["Fecha"], r["Categoría"], r["Descripción"], r["Método"], r["Monto"], r["Origen"]] for r in table],
            ),
            file_name="copymary_reporte_egresos.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("Todavía no hay gastos registrados.")


def render_reports_hub() -> None:
    with st.container(border=True):
        render_page_header(
            "Reportes",
            "Consulta y exporta información consolidada del ERP sin modificar los registros originales.",
        )
        st.caption("Los reportes leen las mismas fuentes de datos utilizadas por Ventas, Compras, Caja, Gastos e Inventario.")

    totals = _financial_totals()
    currency = get_currency()
    overview = st.columns(4)
    overview[0].metric("Ingresos", format_money(totals["income"], currency))
    overview[1].metric("Egresos", format_money(totals["cash_out"], currency))
    overview[2].metric("Saldo", format_money(totals["cash_balance"], currency))
    overview[3].metric("Ventas", str(len(_active_sales(_rows("sales_registry")))))

    tabs = st.tabs((
        "Documentos", "Financiero", "Históricos", "Administrativo", "Consolidado", "Egresos"
    ))
    renderers = (
        _render_documents, _render_financial, _render_history,
        _render_administrative, _render_consolidated, _render_expenses,
    )
    for tab, renderer in zip(tabs, renderers):
        with tab:
            renderer()
