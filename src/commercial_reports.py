"""Reportes comerciales CSV para CopyMary ERP."""

import csv
from io import StringIO

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _get_list(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _csv_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _clients_csv(clients: list[dict]) -> bytes:
    return _csv_bytes(
        ["ID", "Nombre", "Teléfono", "Dirección", "Notas", "Fecha UTC"],
        [
            [
                client.get("client_id", ""),
                client.get("name", ""),
                client.get("phone", ""),
                client.get("address", ""),
                client.get("notes", ""),
                client.get("created_at_utc", ""),
            ]
            for client in clients
        ],
    )


def _sales_csv(sales: list[dict], clients: list[dict], currency: str) -> bytes:
    client_names = {
        str(client.get("client_id", "")): str(client.get("name", "Cliente"))
        for client in clients
    }
    return _csv_bytes(
        [
            "ID venta",
            "Fecha UTC",
            "Cliente",
            "Descripción",
            "Cantidad",
            "Precio unitario",
            "Descuento",
            "Total",
            "Costo estimado",
            "Ganancia estimada",
            "Pago",
            "Estado",
            "Método",
            "Moneda",
            "Notas",
        ],
        [
            [
                sale.get("sale_id", ""),
                sale.get("created_at_utc", ""),
                client_names.get(str(sale.get("client_id", "")), "Sin cliente"),
                sale.get("description", ""),
                f"{float(sale.get('quantity', 0.0)):.4f}",
                f"{float(sale.get('unit_price', 0.0)):.4f}",
                f"{float(sale.get('discount', 0.0)):.4f}",
                f"{float(sale.get('total', 0.0)):.4f}",
                f"{float(sale.get('estimated_cost', 0.0)):.4f}",
                f"{float(sale.get('total', 0.0)) - float(sale.get('estimated_cost', 0.0)):.4f}",
                sale.get("payment_status", ""),
                sale.get("order_status", ""),
                sale.get("payment_method", ""),
                currency,
                sale.get("notes", ""),
            ]
            for sale in sales
        ],
    )


def _cash_csv(movements: list[dict], currency: str) -> bytes:
    return _csv_bytes(
        [
            "ID movimiento",
            "Fecha UTC",
            "Tipo",
            "Categoría",
            "Monto",
            "Método",
            "Referencia",
            "Moneda",
            "Notas",
        ],
        [
            [
                movement.get("movement_id", ""),
                movement.get("created_at_utc", ""),
                movement.get("movement_type", ""),
                movement.get("category", ""),
                f"{float(movement.get('amount', 0.0)):.4f}",
                movement.get("payment_method", ""),
                movement.get("reference", ""),
                currency,
                movement.get("notes", ""),
            ]
            for movement in movements
        ],
    )


def _quotes_csv(quotes: list[dict], clients: list[dict], currency: str) -> bytes:
    client_names = {
        str(client.get("client_id", "")): str(client.get("name", "Cliente"))
        for client in clients
    }
    rows: list[list[object]] = []
    for quote in quotes:
        subtotal = sum(
            float(item.get("quantity", 0.0)) * float(item.get("unit_price", 0.0))
            for item in quote.get("items", [])
            if isinstance(item, dict)
        )
        total = max(subtotal - float(quote.get("discount", 0.0)), 0.0)
        rows.append(
            [
                quote.get("quote_id", ""),
                quote.get("created_at_utc", ""),
                client_names.get(str(quote.get("client_id", "")), "Sin cliente"),
                quote.get("status", ""),
                quote.get("validity_days", 0),
                len(quote.get("items", [])),
                f"{subtotal:.4f}",
                f"{float(quote.get('discount', 0.0)):.4f}",
                f"{total:.4f}",
                currency,
                quote.get("converted_sale_id", ""),
                quote.get("notes", ""),
            ]
        )
    return _csv_bytes(
        [
            "ID cotización",
            "Fecha UTC",
            "Cliente",
            "Estado",
            "Vigencia días",
            "Conceptos",
            "Subtotal",
            "Descuento",
            "Total",
            "Moneda",
            "Venta convertida",
            "Notas",
        ],
        rows,
    )


def render_commercial_reports() -> None:
    with st.container(border=True):
        render_page_header(
            "Reportes comerciales",
            "Consulta indicadores y descarga clientes, ventas, caja y cotizaciones en CSV.",
        )
        st.caption("Los reportes reflejan únicamente los datos de la sesión actual.")

    clients = _get_list("customers_registry")
    sales = _get_list("sales_registry")
    cash = _get_list("cash_movements")
    quotes = _get_list("quotes_registry")
    currency = get_currency()

    paid_sales = [sale for sale in sales if sale.get("payment_status") == "Pagado"]
    pending_sales = [sale for sale in sales if sale.get("payment_status") != "Pagado"]
    income = sum(
        float(movement.get("amount", 0.0))
        for movement in cash
        if movement.get("movement_type") == "Ingreso"
    )
    expenses = sum(
        float(movement.get("amount", 0.0))
        for movement in cash
        if movement.get("movement_type") == "Egreso"
    )
    estimated_profit = sum(
        float(sale.get("total", 0.0)) - float(sale.get("estimated_cost", 0.0))
        for sale in paid_sales
    )

    first = st.columns(4)
    first[0].metric("Clientes", str(len(clients)))
    first[1].metric("Ventas", str(len(sales)))
    first[2].metric("Cotizaciones", str(len(quotes)))
    first[3].metric("Pendientes de pago", str(len(pending_sales)))

    second = st.columns(3)
    second[0].metric("Ingresos", format_money(income, currency))
    second[1].metric("Saldo de caja", format_money(income - expenses, currency))
    second[2].metric("Ganancia estimada", format_money(estimated_profit, currency))

    st.divider()
    st.subheader("Descargas")
    download_columns = st.columns(2)
    with download_columns[0]:
        st.download_button(
            "Descargar clientes",
            data=_clients_csv(clients),
            file_name="copymary_clientes.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not clients,
        )
        st.download_button(
            "Descargar ventas y pedidos",
            data=_sales_csv(sales, clients, currency),
            file_name="copymary_ventas_pedidos.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not sales,
        )
    with download_columns[1]:
        st.download_button(
            "Descargar caja",
            data=_cash_csv(cash, currency),
            file_name="copymary_caja.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not cash,
        )
        st.download_button(
            "Descargar cotizaciones",
            data=_quotes_csv(quotes, clients, currency),
            file_name="copymary_cotizaciones.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not quotes,
        )

    st.subheader("Resumen por método de pago")
    methods: dict[str, float] = {}
    for movement in cash:
        if movement.get("movement_type") != "Ingreso":
            continue
        method = str(movement.get("payment_method", "Otro"))
        methods[method] = methods.get(method, 0.0) + float(movement.get("amount", 0.0))

    if not methods:
        st.info("Todavía no hay ingresos para resumir por método de pago.")
    else:
        for method, amount in sorted(methods.items(), key=lambda item: item[1], reverse=True):
            st.metric(method, format_money(amount, currency))

    render_info_card(
        "Uso de los reportes",
        "Los archivos CSV pueden abrirse en Excel o Google Sheets para análisis, archivo o impresión.",
        "EXPORTACIÓN COMERCIAL",
    )
