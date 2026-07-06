"""Reportes comerciales ampliados para CopyMary ERP."""

from collections import defaultdict
from datetime import date, datetime, timedelta
import csv
import io

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_datetime(value) -> datetime | None:
    raw = str(value or "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.fromisoformat(raw[:10])
        except ValueError:
            return None


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _cancelled(record: dict) -> bool:
    value = str(record.get("order_status", record.get("status", ""))).strip().lower()
    return value in {"cancelado", "cancelada", "anulado", "anulada"}


def _in_range(record: dict, start: date, end: date) -> bool:
    created = _as_datetime(record.get("created_at_utc", record.get("created_at", record.get("date", ""))))
    return bool(created and start <= created.date() <= end)


def _csv_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _sales_export(sales: list[dict], clients: list[dict], currency: str) -> bytes:
    return _csv_bytes(
        ["ID", "Fecha", "Cliente", "Descripción", "Total", "Costo", "Ganancia", "Margen %", "Pago", "Pedido", "Método", "Moneda"],
        [
            [
                sale.get("sale_id", ""),
                sale.get("created_at_utc", ""),
                _client_name(str(sale.get("client_id", "")), clients),
                sale.get("description", ""),
                _num(sale.get("total")),
                _num(sale.get("estimated_cost")),
                _num(sale.get("total")) - _num(sale.get("estimated_cost")),
                ((_num(sale.get("total")) - _num(sale.get("estimated_cost"))) / _num(sale.get("total")) * 100) if _num(sale.get("total")) else 0,
                sale.get("payment_status", ""),
                sale.get("order_status", ""),
                sale.get("payment_method", ""),
                currency,
            ]
            for sale in sales
        ],
    )


def _summary_export(summary_rows: list[list[object]]) -> bytes:
    return _csv_bytes(["Indicador", "Valor"], summary_rows)


def render_commercial_reports_plus() -> None:
    render_page_header(
        "Reportes comerciales",
        "Analiza ventas, clientes, márgenes, cotizaciones y métodos de pago por período.",
    )

    clients = _rows("customers_registry")
    sales_all = [item for item in _rows("sales_registry") if not _cancelled(item)]
    quotes_all = _rows("quotes_registry")
    cash_all = _rows("cash_movements")
    payments_all = [item for item in _rows("payment_records") if not item.get("reversed")]
    currency = get_currency()
    today = date.today()

    st.markdown("### Período del reporte")
    filters = st.columns(3)
    period = filters[0].selectbox("Período", ("Este mes", "Mes anterior", "Últimos 30 días", "Este año", "Personalizado"))
    if period == "Este mes":
        start = today.replace(day=1)
        end = today
    elif period == "Mes anterior":
        first_current = today.replace(day=1)
        end = first_current - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "Últimos 30 días":
        start = today - timedelta(days=29)
        end = today
    elif period == "Este año":
        start = date(today.year, 1, 1)
        end = today
    else:
        start = filters[1].date_input("Desde", value=today.replace(day=1))
        end = filters[2].date_input("Hasta", value=today)
    if start > end:
        st.error("La fecha inicial no puede ser posterior a la fecha final.")
        return

    sales = [item for item in sales_all if _in_range(item, start, end)]
    quotes = [item for item in quotes_all if _in_range(item, start, end)]
    cash = [item for item in cash_all if _in_range(item, start, end)]
    payments = [item for item in payments_all if _in_range(item, start, end)]

    revenue = sum(_num(item.get("total")) for item in sales)
    costs = sum(_num(item.get("estimated_cost")) for item in sales)
    profit = revenue - costs
    margin = profit / revenue * 100 if revenue else 0.0
    average_ticket = revenue / len(sales) if sales else 0.0
    paid_sales = [item for item in sales if str(item.get("payment_status", "")) == "Pagado"]
    pending_sales = [item for item in sales if str(item.get("payment_status", "")) != "Pagado"]
    converted_quotes = [item for item in quotes if item.get("converted_sale_id")]
    conversion = len(converted_quotes) / len(quotes) * 100 if quotes else 0.0

    first = st.columns(5)
    first[0].metric("Ventas", str(len(sales)))
    first[1].metric("Facturación", format_money(revenue, currency))
    first[2].metric("Ganancia estimada", format_money(profit, currency))
    first[3].metric("Margen", f"{margin:,.1f}%")
    first[4].metric("Ticket promedio", format_money(average_ticket, currency))

    second = st.columns(4)
    second[0].metric("Cotizaciones", str(len(quotes)))
    second[1].metric("Conversión", f"{conversion:,.1f}%")
    second[2].metric("Ventas pagadas", str(len(paid_sales)))
    second[3].metric("Pendientes de pago", str(len(pending_sales)))

    if margin < 30 and revenue > 0:
        st.warning("El margen estimado del período está por debajo del 30%.")
    if pending_sales:
        pending_total = sum(_num(item.get("total")) for item in pending_sales)
        st.warning(f"Hay {len(pending_sales)} venta(s) pendientes por {format_money(pending_total, currency)}.")

    st.markdown("### Tendencia diaria")
    daily: dict[str, float] = defaultdict(float)
    for sale in sales:
        created = _as_datetime(sale.get("created_at_utc"))
        if created:
            daily[created.date().isoformat()] += _num(sale.get("total"))
    if daily:
        st.bar_chart({"Ventas": dict(sorted(daily.items()))})
    else:
        st.info("No hay ventas en el período seleccionado.")

    client_totals: dict[str, float] = defaultdict(float)
    product_totals: dict[str, float] = defaultdict(float)
    for sale in sales:
        client_totals[_client_name(str(sale.get("client_id", "")), clients)] += _num(sale.get("total"))
        product_totals[str(sale.get("description", "Sin descripción"))] += _num(sale.get("total"))

    ranking_columns = st.columns(2)
    with ranking_columns[0]:
        st.markdown("### Clientes principales")
        if not client_totals:
            st.info("Sin datos de clientes en el período.")
        for name, amount in sorted(client_totals.items(), key=lambda item: item[1], reverse=True)[:10]:
            st.write(f"**{name}:** {format_money(amount, currency)}")
    with ranking_columns[1]:
        st.markdown("### Productos o servicios principales")
        if not product_totals:
            st.info("Sin productos o servicios vendidos en el período.")
        for name, amount in sorted(product_totals.items(), key=lambda item: item[1], reverse=True)[:10]:
            st.write(f"**{name}:** {format_money(amount, currency)}")

    st.markdown("### Métodos de pago")
    methods: dict[str, float] = defaultdict(float)
    for payment in payments:
        method = str(payment.get("payment_method", payment.get("method", "Otro")))
        methods[method] += _num(payment.get("amount"))
    if not methods:
        for movement in cash:
            if str(movement.get("movement_type", "")) == "Ingreso":
                methods[str(movement.get("payment_method", "Otro"))] += _num(movement.get("amount"))
    if not methods:
        st.info("No hay cobros registrados en el período.")
    else:
        method_columns = st.columns(min(len(methods), 4))
        for index, (method, amount) in enumerate(sorted(methods.items(), key=lambda item: item[1], reverse=True)):
            method_columns[index % len(method_columns)].metric(method, format_money(amount, currency))

    st.markdown("### Descargas del período")
    downloads = st.columns(2)
    downloads[0].download_button(
        "Descargar ventas filtradas",
        data=_sales_export(sales, clients, currency),
        file_name=f"ventas_{start.isoformat()}_{end.isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not sales,
    )
    downloads[1].download_button(
        "Descargar resumen ejecutivo",
        data=_summary_export([
            ["Período", f"{start.isoformat()} a {end.isoformat()}"],
            ["Ventas", len(sales)],
            ["Facturación", revenue],
            ["Costos estimados", costs],
            ["Ganancia estimada", profit],
            ["Margen %", margin],
            ["Ticket promedio", average_ticket],
            ["Cotizaciones", len(quotes)],
            ["Conversión %", conversion],
            ["Pendientes de pago", len(pending_sales)],
        ]),
        file_name=f"resumen_comercial_{start.isoformat()}_{end.isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    render_info_card(
        "Lectura del reporte",
        "Los indicadores se calculan con la información registrada en la sesión y respetan el período seleccionado.",
        "ANÁLISIS COMERCIAL",
    )
