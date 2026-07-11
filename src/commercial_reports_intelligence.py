"""Comparativos, retención y proyección para reportes comerciales."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from html import escape

import streamlit as st

from src import commercial_reports_plus as base
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import read_list as _rows


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


def _cancelled(record: dict) -> bool:
    value = str(record.get("order_status", record.get("status", ""))).strip().lower()
    return value in {"cancelado", "cancelada", "anulado", "anulada"}


def _month_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    if day.month == 12:
        next_month = date(day.year + 1, 1, 1)
    else:
        next_month = date(day.year, day.month + 1, 1)
    return start, next_month - timedelta(days=1)


def _previous_month(day: date) -> tuple[date, date]:
    current_start = day.replace(day=1)
    previous_end = current_start - timedelta(days=1)
    return _month_bounds(previous_end)


def _in_range(record: dict, start: date, end: date) -> bool:
    created = _as_datetime(record.get("created_at_utc", record.get("created_at", record.get("date", ""))))
    return bool(created and start <= created.date() <= end)


def _pct_change(current: float, previous: float) -> str:
    if previous == 0:
        return "Sin base anterior" if current else "0.0%"
    return f"{(current - previous) / previous * 100:+,.1f}%"


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _executive_html(
    current_label: str,
    previous_label: str,
    current_revenue: float,
    previous_revenue: float,
    current_profit: float,
    previous_profit: float,
    current_orders: int,
    previous_orders: int,
    average_ticket: float,
    retention: float,
    forecast: float,
    top_clients: list[tuple[str, float]],
    top_products: list[tuple[str, float]],
) -> bytes:
    currency = get_currency()
    client_rows = "".join(
        f"<tr><td>{escape(name)}</td><td>{escape(format_money(amount, currency))}</td></tr>"
        for name, amount in top_clients
    )
    product_rows = "".join(
        f"<tr><td>{escape(name)}</td><td>{escape(format_money(amount, currency))}</td></tr>"
        for name, amount in top_products
    )
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Informe comercial</title>
<style>body{{font-family:Arial,sans-serif;margin:36px;color:#1f2937}}h1{{color:#6d4aff}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.card{{border:1px solid #e5e7eb;border-radius:12px;padding:14px}}table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{border:1px solid #e5e7eb;padding:9px;text-align:left}}th{{background:#f8fafc}}.muted{{color:#64748b}}</style></head><body>
<h1>Informe ejecutivo comercial</h1><p class="muted">Comparación: {escape(current_label)} frente a {escape(previous_label)}</p>
<div class="grid"><div class="card"><strong>Facturación</strong><br>{escape(format_money(current_revenue, currency))}<br>{escape(_pct_change(current_revenue, previous_revenue))}</div><div class="card"><strong>Ganancia estimada</strong><br>{escape(format_money(current_profit, currency))}<br>{escape(_pct_change(current_profit, previous_profit))}</div><div class="card"><strong>Pedidos</strong><br>{current_orders}<br>{escape(_pct_change(float(current_orders), float(previous_orders)))}</div><div class="card"><strong>Ticket promedio</strong><br>{escape(format_money(average_ticket, currency))}</div><div class="card"><strong>Retención</strong><br>{retention:,.1f}%</div><div class="card"><strong>Proyección mensual</strong><br>{escape(format_money(forecast, currency))}</div></div>
<h2>Clientes principales</h2><table><tr><th>Cliente</th><th>Facturación</th></tr>{client_rows}</table>
<h2>Productos o servicios principales</h2><table><tr><th>Producto o servicio</th><th>Facturación</th></tr>{product_rows}</table>
</body></html>"""
    return html.encode("utf-8")


def render_commercial_reports_intelligence() -> None:
    render_page_header(
        "Reportes comerciales",
        "Compara períodos, mide retención y proyecta el comportamiento comercial del negocio.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_commercial_reports_plus()
    finally:
        base.render_page_header = original_header

    sales = [item for item in _rows("sales_registry") if not _cancelled(item)]
    clients = _rows("customers_registry")
    today = date.today()
    current_start, current_end = _month_bounds(today)
    previous_start, previous_end = _previous_month(today)
    current_sales = [item for item in sales if _in_range(item, current_start, min(current_end, today))]
    previous_sales = [item for item in sales if _in_range(item, previous_start, previous_end)]

    def revenue(rows: list[dict]) -> float:
        return sum(_num(item.get("total")) for item in rows)

    def profit(rows: list[dict]) -> float:
        return sum(_num(item.get("total")) - _num(item.get("estimated_cost")) for item in rows)

    current_revenue = revenue(current_sales)
    previous_revenue = revenue(previous_sales)
    current_profit = profit(current_sales)
    previous_profit = profit(previous_sales)
    average_ticket = current_revenue / len(current_sales) if current_sales else 0.0

    st.divider()
    st.markdown("### Comparación mensual")
    compare = st.columns(4)
    compare[0].metric("Facturación actual", format_money(current_revenue), _pct_change(current_revenue, previous_revenue))
    compare[1].metric("Ganancia actual", format_money(current_profit), _pct_change(current_profit, previous_profit))
    compare[2].metric("Pedidos actuales", str(len(current_sales)), _pct_change(float(len(current_sales)), float(len(previous_sales))))
    compare[3].metric("Ticket promedio", format_money(average_ticket))

    current_client_ids = {str(item.get("client_id", "")) for item in current_sales if item.get("client_id")}
    previous_client_ids = {str(item.get("client_id", "")) for item in previous_sales if item.get("client_id")}
    recurrent_ids = current_client_ids & previous_client_ids
    new_ids = current_client_ids - previous_client_ids
    retention = len(recurrent_ids) / len(previous_client_ids) * 100 if previous_client_ids else 0.0

    st.markdown("### Clientes nuevos y recurrentes")
    client_metrics = st.columns(4)
    client_metrics[0].metric("Clientes del mes", str(len(current_client_ids)))
    client_metrics[1].metric("Nuevos", str(len(new_ids)))
    client_metrics[2].metric("Recurrentes", str(len(recurrent_ids)))
    client_metrics[3].metric("Retención", f"{retention:,.1f}%")

    if previous_client_ids and retention < 40:
        st.warning("La retención mensual está por debajo del 40%; conviene reactivar clientes anteriores.")

    elapsed_days = max(today.day, 1)
    days_in_month = current_end.day
    forecast = current_revenue / elapsed_days * days_in_month if current_revenue else 0.0
    forecast_orders = len(current_sales) / elapsed_days * days_in_month if current_sales else 0.0
    st.markdown("### Proyección al cierre del mes")
    forecast_columns = st.columns(3)
    forecast_columns[0].metric("Facturación proyectada", format_money(forecast))
    forecast_columns[1].metric("Pedidos proyectados", f"{forecast_orders:,.1f}")
    forecast_columns[2].metric("Días transcurridos", f"{elapsed_days} de {days_in_month}")
    st.caption("La proyección usa el ritmo promedio diario del mes actual y no sustituye una meta comercial.")

    st.markdown("### Flujo de pedidos")
    statuses = Counter(str(item.get("order_status", "Pendiente")) for item in current_sales)
    status_columns = st.columns(min(max(len(statuses), 1), 5))
    if not statuses:
        st.info("No hay pedidos en el mes actual.")
    else:
        for index, (status, count) in enumerate(statuses.most_common()):
            status_columns[index % len(status_columns)].metric(status, str(count))

    client_totals: dict[str, float] = defaultdict(float)
    product_totals: dict[str, float] = defaultdict(float)
    for sale in current_sales:
        client_totals[_client_name(str(sale.get("client_id", "")), clients)] += _num(sale.get("total"))
        product_totals[str(sale.get("description", "Sin descripción"))] += _num(sale.get("total"))
    top_clients = sorted(client_totals.items(), key=lambda item: item[1], reverse=True)[:5]
    top_products = sorted(product_totals.items(), key=lambda item: item[1], reverse=True)[:5]

    current_label = f"{current_start.isoformat()} a {min(current_end, today).isoformat()}"
    previous_label = f"{previous_start.isoformat()} a {previous_end.isoformat()}"
    st.download_button(
        "Descargar informe ejecutivo HTML",
        data=_executive_html(
            current_label,
            previous_label,
            current_revenue,
            previous_revenue,
            current_profit,
            previous_profit,
            len(current_sales),
            len(previous_sales),
            average_ticket,
            retention,
            forecast,
            top_clients,
            top_products,
        ),
        file_name=f"informe_comercial_{today.isoformat()}.html",
        mime="text/html",
        use_container_width=True,
    )

    render_info_card(
        "Inteligencia comercial",
        "Los comparativos, la retención y la proyección se calculan con los registros disponibles en la sesión.",
        "INFORME EJECUTIVO",
    )
