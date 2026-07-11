"""Tendencias, retención, metas y exportación del Panel comercial."""

from datetime import date, datetime, timedelta
import csv
import io

import streamlit as st

from src import commercial_dashboard_plus as base
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import read_list as _rows


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _record_datetime(record: dict) -> datetime | None:
    raw = str(record.get("created_at_utc", record.get("created_at", record.get("date", ""))))
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.fromisoformat(raw[:10])
        except ValueError:
            return None


def _record_month(record: dict) -> str:
    value = _record_datetime(record)
    return value.strftime("%Y-%m") if value else ""


def _shift_month(month: str, offset: int) -> str:
    year, number = (int(part) for part in month.split("-"))
    absolute = year * 12 + number - 1 + offset
    return f"{absolute // 12}-{absolute % 12 + 1:02d}"


def _active_sales(month: str) -> list[dict]:
    cancelled = {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    return [
        sale for sale in _rows("sales_registry")
        if sale.get("order_status") not in cancelled and _record_month(sale) == month
    ]


def _goals(month: str) -> dict:
    raw = st.session_state.get("business_goals", {})
    if not isinstance(raw, dict):
        return {}
    values = raw.get(month, {})
    return dict(values) if isinstance(values, dict) else {}


def _quote_total(quote: dict) -> float:
    subtotal = sum(
        _number(item.get("quantity")) * _number(item.get("unit_price"))
        for item in quote.get("items", [])
        if isinstance(item, dict)
    )
    return max(subtotal - _number(quote.get("discount")), 0.0)


def _trend_rows(selected_month: str) -> list[dict]:
    rows: list[dict] = []
    for offset in range(-5, 1):
        month = _shift_month(selected_month, offset)
        sales = _active_sales(month)
        revenue = sum(_number(item.get("total")) for item in sales)
        profit = sum(_number(item.get("total")) - _number(item.get("estimated_cost")) for item in sales)
        rows.append({"Mes": month, "Ventas": revenue, "Ganancia": profit, "Pedidos": len(sales)})
    return rows


def _customer_segments(selected_month: str) -> tuple[int, int, int]:
    sales = [
        sale for sale in _rows("sales_registry")
        if sale.get("order_status") not in {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    ]
    current_ids = {str(item.get("client_id", "")) for item in sales if _record_month(item) == selected_month and item.get("client_id")}
    earlier_ids = {str(item.get("client_id", "")) for item in sales if _record_month(item) and _record_month(item) < selected_month and item.get("client_id")}
    new_clients = len(current_ids - earlier_ids)
    recurrent = len(current_ids & earlier_ids)
    without_client = sum(1 for item in sales if _record_month(item) == selected_month and not item.get("client_id"))
    return new_clients, recurrent, without_client


def _expiring_quotes(selected_month: str) -> list[dict]:
    today = date.today()
    result: list[dict] = []
    for quote in _rows("quotes_registry"):
        if quote.get("converted_sale_id") or quote.get("status") == "Convertida":
            continue
        created = _record_datetime(quote)
        if not created:
            continue
        expiry = created.date() + timedelta(days=int(_number(quote.get("validity_days"), 7)))
        remaining = (expiry - today).days
        if _record_month(quote) == selected_month and remaining <= 7:
            result.append({
                "quote_id": str(quote.get("quote_id", "")),
                "expiry": expiry.isoformat(),
                "remaining": remaining,
                "total": _quote_total(quote),
            })
    return sorted(result, key=lambda item: item["remaining"])


def _csv_report(month: str, trends: list[dict], expiring: list[dict], new_clients: int, recurrent: int) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Panel comercial CopyMary ERP", month])
    writer.writerow(["Generado", datetime.now().isoformat(timespec="seconds")])
    writer.writerow([])
    writer.writerow(["Clientes nuevos", new_clients])
    writer.writerow(["Clientes recurrentes", recurrent])
    writer.writerow([])
    writer.writerow(["Mes", "Ventas", "Ganancia", "Pedidos"])
    for row in trends:
        writer.writerow([row["Mes"], row["Ventas"], row["Ganancia"], row["Pedidos"]])
    writer.writerow([])
    writer.writerow(["Cotización", "Vencimiento", "Días restantes", "Total"])
    for item in expiring:
        writer.writerow([item["quote_id"], item["expiry"], item["remaining"], item["total"]])
    return buffer.getvalue().encode("utf-8-sig")


def render_commercial_dashboard_insights() -> None:
    render_page_header(
        "Panel comercial",
        "Resultados, tendencias, clientes y oportunidades para orientar las próximas decisiones de venta.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_commercial_dashboard_plus()
    finally:
        base.render_page_header = original_header

    month = str(st.session_state.get("commercial_dashboard_month", date.today().strftime("%Y-%m")))
    trends = _trend_rows(month)
    new_clients, recurrent, without_client = _customer_segments(month)
    expiring = _expiring_quotes(month)

    st.divider()
    st.markdown("### Tendencia de seis meses")
    st.dataframe(trends, use_container_width=True, hide_index=True)

    latest = trends[-1]
    previous = trends[-2] if len(trends) > 1 else {"Ventas": 0.0, "Ganancia": 0.0, "Pedidos": 0}
    trend_metrics = st.columns(3)
    trend_metrics[0].metric("Cambio en ventas", format_money(latest["Ventas"] - previous["Ventas"]))
    trend_metrics[1].metric("Cambio en ganancia", format_money(latest["Ganancia"] - previous["Ganancia"]))
    trend_metrics[2].metric("Cambio en pedidos", str(int(latest["Pedidos"] - previous["Pedidos"])))

    st.markdown("### Clientes nuevos y recurrentes")
    client_metrics = st.columns(3)
    client_metrics[0].metric("Clientes nuevos", str(new_clients))
    client_metrics[1].metric("Clientes recurrentes", str(recurrent))
    client_metrics[2].metric("Ventas sin cliente", str(without_client))
    known_clients = new_clients + recurrent
    retention = recurrent / known_clients * 100 if known_clients else 0.0
    st.progress(min(retention / 100, 1.0))
    st.caption(f"Proporción de clientes recurrentes en el mes: {retention:,.1f}%.")

    st.markdown("### Avance contra metas comerciales")
    goals = _goals(month)
    sales_goal = _number(goals.get("sales_goal"))
    profit_goal = _number(goals.get("profit_goal"))
    orders_goal = _number(goals.get("orders_goal"))
    goal_rows = (
        ("Ventas", _number(latest["Ventas"]), sales_goal, True),
        ("Ganancia", _number(latest["Ganancia"]), profit_goal, True),
        ("Pedidos", _number(latest["Pedidos"]), orders_goal, False),
    )
    goal_columns = st.columns(3)
    for index, (label, current, target, money) in enumerate(goal_rows):
        with goal_columns[index]:
            target_text = format_money(target) if money else str(int(target))
            current_text = format_money(current) if money else str(int(current))
            st.metric(label, current_text, f"Meta {target_text}" if target > 0 else "Sin meta")
            if target > 0:
                st.progress(min(max(current / target, 0.0), 1.0))
                st.caption(f"Avance: {current / target * 100:,.1f}%")
            else:
                st.caption("Define esta meta en Metas del negocio.")

    st.markdown("### Cotizaciones que requieren seguimiento")
    if not expiring:
        st.success("No hay cotizaciones del mes vencidas o próximas a vencer en los próximos siete días.")
    else:
        for item in expiring[:10]:
            with st.container(border=True):
                columns = st.columns([2, 1, 1])
                columns[0].markdown(f"#### Cotización {item['quote_id']}")
                columns[0].caption(f"Vence: {item['expiry']}")
                columns[1].metric("Días restantes", str(item["remaining"]))
                columns[2].metric("Total", format_money(item["total"]))
        if st.button("Abrir cotizaciones", key="commercial_follow_quotes", use_container_width=True, type="primary"):
            st.session_state["pending_navigation_area"] = "Ventas y clientes"
            st.session_state["pending_navigation_page"] = "Cotizaciones"
            st.rerun()

    st.download_button(
        "Descargar informe comercial CSV",
        data=_csv_report(month, trends, expiring, new_clients, recurrent),
        file_name=f"panel_comercial_{month}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    render_info_card(
        "Seguimiento comercial ampliado",
        "La tendencia, la recurrencia de clientes, las metas y las cotizaciones se calculan con los datos de la sesión actual.",
        "ANÁLISIS COMERCIAL",
    )
