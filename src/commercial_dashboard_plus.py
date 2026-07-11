"""Panel comercial avanzado para CopyMary ERP."""

from collections import Counter, defaultdict
from datetime import date, datetime

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import read_list as _rows


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _record_month(record: dict) -> str:
    raw = str(record.get("created_at_utc", record.get("created_at", record.get("date", ""))))
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return raw[:7] if len(raw) >= 7 else ""


def _previous_month(month: str) -> str:
    year, number = (int(part) for part in month.split("-"))
    if number == 1:
        return f"{year - 1}-12"
    return f"{year}-{number - 1:02d}"


def _go(area: str, page: str) -> None:
    st.session_state["pending_navigation_area"] = area
    st.session_state["pending_navigation_page"] = page
    st.rerun()


def _button(label: str, area: str, page: str, key: str, primary: bool = False) -> None:
    if st.button(label, key=key, use_container_width=True, type="primary" if primary else "secondary"):
        _go(area, page)


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _sale_paid(sale: dict, payments: list[dict]) -> float:
    sale_id = str(sale.get("sale_id", ""))
    explicit = sum(
        _number(item.get("amount"))
        for item in payments
        if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
    )
    total = _number(sale.get("total"))
    if explicit > 0:
        return min(explicit, total)
    if sale.get("payment_status") == "Pagado":
        return total
    return 0.0


def _period_sales(sales: list[dict], month: str) -> list[dict]:
    cancelled = {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    return [
        sale for sale in sales
        if sale.get("order_status") not in cancelled and _record_month(sale) == month
    ]


def render_commercial_dashboard_plus() -> None:
    render_page_header(
        "Panel comercial",
        "Ventas, clientes, pedidos, conversión y cobros reunidos para tomar decisiones comerciales.",
    )

    clients = _rows("customers_registry")
    sales = _rows("sales_registry")
    quotes = _rows("quotes_registry")
    payments = _rows("payment_records")
    inventory = _rows("inventory_registry")

    current_month = date.today().strftime("%Y-%m")
    months = {current_month}
    months.update(filter(None, (_record_month(item) for item in sales + quotes)))
    month = st.selectbox("Mes de análisis", sorted(months, reverse=True), key="commercial_dashboard_month")
    previous = _previous_month(month)

    current_sales = _period_sales(sales, month)
    previous_sales = _period_sales(sales, previous)
    current_quotes = [quote for quote in quotes if _record_month(quote) == month]

    total_sales = sum(_number(item.get("total")) for item in current_sales)
    previous_total = sum(_number(item.get("total")) for item in previous_sales)
    total_profit = sum(_number(item.get("total")) - _number(item.get("estimated_cost")) for item in current_sales)
    previous_profit = sum(_number(item.get("total")) - _number(item.get("estimated_cost")) for item in previous_sales)
    ticket = total_sales / len(current_sales) if current_sales else 0.0
    previous_ticket = previous_total / len(previous_sales) if previous_sales else 0.0

    converted_quotes = sum(1 for item in current_quotes if item.get("converted_sale_id"))
    conversion = converted_quotes / len(current_quotes) * 100 if current_quotes else 0.0

    pending_orders = [
        item for item in current_sales
        if item.get("order_status") not in {"Entregado", "Entregada"}
    ]
    ready_orders = [item for item in current_sales if item.get("order_status") == "Listo"]
    receivables = sum(max(_number(item.get("total")) - _sale_paid(item, payments), 0.0) for item in current_sales)

    first = st.columns(4)
    first[0].metric(
        "Ventas del mes",
        format_money(total_sales),
        format_money(total_sales - previous_total) if previous_sales else None,
    )
    first[1].metric(
        "Ganancia estimada",
        format_money(total_profit),
        format_money(total_profit - previous_profit) if previous_sales else None,
    )
    first[2].metric(
        "Ticket promedio",
        format_money(ticket),
        format_money(ticket - previous_ticket) if previous_sales else None,
    )
    first[3].metric("Conversión de cotizaciones", f"{conversion:,.1f}%")

    second = st.columns(4)
    second[0].metric("Pedidos del mes", str(len(current_sales)))
    second[1].metric("Pedidos pendientes", str(len(pending_orders)))
    second[2].metric("Listos para entregar", str(len(ready_orders)))
    second[3].metric("Por cobrar", format_money(receivables))

    st.markdown("### Estado comercial")
    if receivables > 0:
        st.warning(f"Hay {format_money(receivables)} pendiente por cobrar en el mes seleccionado.")
    elif current_sales:
        st.success("Todas las ventas del período aparecen pagadas.")
    else:
        st.info("Todavía no hay ventas registradas en el período.")

    st.markdown("### Acciones rápidas")
    actions = st.columns(4)
    with actions[0]:
        render_info_card("Clientes", "Registra nuevos clientes y revisa su historial.", "GESTIÓN COMERCIAL")
        _button("Abrir clientes", "Ventas y clientes", "Clientes", "commercial_clients")
    with actions[1]:
        render_info_card("Ventas", "Crea pedidos y actualiza sus estados.", "OPERACIÓN")
        _button("Nueva venta", "Ventas y clientes", "Ventas y pedidos", "commercial_sales", True)
    with actions[2]:
        render_info_card("Cotizaciones", "Prepara propuestas y conviértelas en ventas.", "CONVERSIÓN")
        _button("Abrir cotizaciones", "Ventas y clientes", "Cotizaciones", "commercial_quotes")
    with actions[3]:
        render_info_card("Cobros", "Da seguimiento a los saldos pendientes.", "LIQUIDEZ")
        _button("Abrir cuentas por cobrar", "Ventas y clientes", "Cuentas por cobrar", "commercial_receivables", bool(receivables))

    st.markdown("### Embudo comercial")
    funnel = st.columns(4)
    funnel[0].metric("Cotizaciones", str(len(current_quotes)))
    funnel[1].metric("Convertidas", str(converted_quotes))
    funnel[2].metric("Pedidos activos", str(len(pending_orders)))
    funnel[3].metric("Entregados", str(sum(1 for item in current_sales if item.get("order_status") in {"Entregado", "Entregada"})))

    st.markdown("### Rendimiento por producto o servicio")
    product_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"sales": 0.0, "profit": 0.0, "orders": 0.0})
    for sale in current_sales:
        name = str(sale.get("description", "Sin descripción")).strip() or "Sin descripción"
        product_totals[name]["sales"] += _number(sale.get("total"))
        product_totals[name]["profit"] += _number(sale.get("total")) - _number(sale.get("estimated_cost"))
        product_totals[name]["orders"] += 1

    if not product_totals:
        st.info("No hay datos suficientes para mostrar productos o servicios destacados.")
    else:
        ranking = sorted(product_totals.items(), key=lambda item: item[1]["sales"], reverse=True)[:8]
        for name, values in ranking:
            with st.container(border=True):
                columns = st.columns([3, 1, 1, 1])
                columns[0].markdown(f"#### {name}")
                columns[1].metric("Ventas", format_money(values["sales"]))
                columns[2].metric("Ganancia", format_money(values["profit"]))
                columns[3].metric("Pedidos", str(int(values["orders"])))

    st.markdown("### Clientes principales")
    client_totals: dict[str, float] = defaultdict(float)
    client_orders: Counter[str] = Counter()
    for sale in current_sales:
        client_id = str(sale.get("client_id", ""))
        name = _client_name(client_id, clients)
        client_totals[name] += _number(sale.get("total"))
        client_orders[name] += 1

    if not client_totals:
        st.info("No hay clientes con ventas en el período seleccionado.")
    else:
        for name, amount in sorted(client_totals.items(), key=lambda item: item[1], reverse=True)[:5]:
            with st.container(border=True):
                columns = st.columns([3, 1, 1])
                columns[0].markdown(f"#### {name}")
                columns[1].metric("Facturado", format_money(amount))
                columns[2].metric("Pedidos", str(client_orders[name]))

    st.markdown("### Situación de pedidos")
    status_counts = Counter(str(item.get("order_status", "Pendiente")) for item in current_sales)
    status_columns = st.columns(5)
    for index, status in enumerate(("Pendiente", "En proceso", "Listo", "Entregado", "Cancelado")):
        status_columns[index].metric(status, str(status_counts.get(status, 0)))

    low_stock = []
    for item in inventory:
        available = _number(item.get("available_quantity", item.get("quantity", 0.0)))
        minimum = _number(item.get("minimum_stock", item.get("reorder_point", 0.0)))
        if minimum > 0 and available <= minimum:
            low_stock.append(item)
    if low_stock:
        st.warning(f"Hay {len(low_stock)} material(es) bajos que podrían afectar nuevos pedidos.")
        _button("Revisar alertas de inventario", "Productos e inventario", "Alertas de inventario", "commercial_inventory")

    render_info_card(
        "Lectura del panel",
        f"Resultados comerciales calculados para {month}. Usa los accesos para actuar sobre ventas, clientes, cotizaciones y cobros.",
        "PANEL COMERCIAL",
    )
