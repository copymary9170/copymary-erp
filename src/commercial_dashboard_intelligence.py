"""Pronóstico, cobranza y oportunidades para el Panel comercial."""

from collections import defaultdict
from datetime import date, datetime

import streamlit as st

from src import commercial_dashboard_insights as base
from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


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
    return total if sale.get("payment_status") == "Pagado" else 0.0


def _go(area: str, page: str) -> None:
    st.session_state["pending_navigation_area"] = area
    st.session_state["pending_navigation_page"] = page
    st.rerun()


def render_commercial_dashboard_intelligence() -> None:
    render_page_header(
        "Panel comercial",
        "Pronóstico de ventas, cobranza, clientes inactivos y rentabilidad para convertir los datos en acciones.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_commercial_dashboard_insights()
    finally:
        base.render_page_header = original_header

    clients = _rows("customers_registry")
    sales = [
        item for item in _rows("sales_registry")
        if item.get("order_status") not in {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    ]
    payments = _rows("payment_records")
    month = str(st.session_state.get("commercial_dashboard_month", date.today().strftime("%Y-%m")))
    current_sales = [item for item in sales if _record_month(item) == month]

    today = date.today()
    year, number = (int(part) for part in month.split("-"))
    current_month_selected = (year, number) == (today.year, today.month)
    elapsed_days = today.day if current_month_selected else 0
    total_days = 31
    if number in {4, 6, 9, 11}:
        total_days = 30
    elif number == 2:
        leap = year % 400 == 0 or (year % 4 == 0 and year % 100 != 0)
        total_days = 29 if leap else 28

    revenue = sum(_number(item.get("total")) for item in current_sales)
    profit = sum(_number(item.get("total")) - _number(item.get("estimated_cost")) for item in current_sales)
    orders = len(current_sales)
    forecast_revenue = revenue / elapsed_days * total_days if elapsed_days else revenue
    forecast_profit = profit / elapsed_days * total_days if elapsed_days else profit
    forecast_orders = orders / elapsed_days * total_days if elapsed_days else float(orders)

    st.divider()
    st.markdown("### Pronóstico al cierre del mes")
    forecast_columns = st.columns(3)
    forecast_columns[0].metric("Ventas proyectadas", format_money(forecast_revenue))
    forecast_columns[1].metric("Ganancia proyectada", format_money(forecast_profit))
    forecast_columns[2].metric("Pedidos proyectados", f"{forecast_orders:,.1f}")
    if current_month_selected and elapsed_days:
        st.caption(f"Proyección calculada con {elapsed_days} día(s) transcurridos de {total_days}.")
    else:
        st.caption("Para meses cerrados, la proyección coincide con el resultado registrado.")

    st.markdown("### Antigüedad de cuentas por cobrar")
    aging = {"0–7 días": 0.0, "8–15 días": 0.0, "16–30 días": 0.0, "Más de 30 días": 0.0}
    aging_count = {key: 0 for key in aging}
    receivable_rows: list[tuple[str, float, int]] = []
    for sale in sales:
        balance = max(_number(sale.get("total")) - _sale_paid(sale, payments), 0.0)
        if balance <= 0:
            continue
        created = _record_datetime(sale)
        age = max((today - created.date()).days, 0) if created else 0
        if age <= 7:
            bucket = "0–7 días"
        elif age <= 15:
            bucket = "8–15 días"
        elif age <= 30:
            bucket = "16–30 días"
        else:
            bucket = "Más de 30 días"
        aging[bucket] += balance
        aging_count[bucket] += 1
        receivable_rows.append((_client_name(str(sale.get("client_id", "")), clients), balance, age))

    aging_columns = st.columns(4)
    for index, bucket in enumerate(aging):
        aging_columns[index].metric(bucket, format_money(aging[bucket]), f"{aging_count[bucket]} cuenta(s)")

    overdue = sorted((item for item in receivable_rows if item[2] > 30), key=lambda item: item[1], reverse=True)
    if overdue:
        st.error(f"Hay {len(overdue)} cuenta(s) con más de 30 días de antigüedad.")
        for client, balance, age in overdue[:5]:
            st.write(f"**{client}** · {format_money(balance)} · {age} días")
        if st.button("Abrir cuentas por cobrar", key="commercial_intel_receivables", use_container_width=True, type="primary"):
            _go("Ventas y clientes", "Cuentas por cobrar")
    elif receivable_rows:
        st.warning("Hay saldos pendientes, pero ninguno supera los 30 días.")
    else:
        st.success("No hay cuentas por cobrar pendientes.")

    st.markdown("### Clientes para reactivar")
    last_purchase: dict[str, datetime] = {}
    lifetime_value: dict[str, float] = defaultdict(float)
    for sale in sales:
        client_id = str(sale.get("client_id", ""))
        created = _record_datetime(sale)
        if not client_id or not created:
            continue
        lifetime_value[client_id] += _number(sale.get("total"))
        if client_id not in last_purchase or created > last_purchase[client_id]:
            last_purchase[client_id] = created

    inactive = []
    for client_id, last_date in last_purchase.items():
        inactive_days = (today - last_date.date()).days
        if inactive_days >= 60:
            inactive.append((client_id, inactive_days, lifetime_value[client_id]))
    inactive.sort(key=lambda item: (item[2], item[1]), reverse=True)

    if not inactive:
        st.success("No hay clientes con 60 días o más sin comprar.")
    else:
        for client_id, days, value in inactive[:8]:
            with st.container(border=True):
                columns = st.columns([3, 1, 1])
                columns[0].markdown(f"#### {_client_name(client_id, clients)}")
                columns[1].metric("Días inactivo", str(days))
                columns[2].metric("Valor histórico", format_money(value))
        if st.button("Abrir clientes", key="commercial_intel_clients", use_container_width=True):
            _go("Ventas y clientes", "Clientes")

    st.markdown("### Riesgos de rentabilidad")
    low_margin = []
    heavy_discount = []
    for sale in current_sales:
        total = _number(sale.get("total"))
        cost = _number(sale.get("estimated_cost"))
        discount = _number(sale.get("discount"))
        margin = (total - cost) / total * 100 if total > 0 else 0.0
        if total > 0 and margin < 30:
            low_margin.append((sale, margin))
        if discount > 0 and discount / max(total + discount, 1.0) >= 0.10:
            heavy_discount.append(sale)

    risk_columns = st.columns(3)
    risk_columns[0].metric("Ventas con margen menor a 30%", str(len(low_margin)))
    risk_columns[1].metric("Descuentos de 10% o más", str(len(heavy_discount)))
    risk_columns[2].metric(
        "Descuentos del mes",
        format_money(sum(_number(item.get("discount")) for item in current_sales)),
    )

    if low_margin:
        with st.expander("Revisar ventas de margen bajo", expanded=False):
            for sale, margin in sorted(low_margin, key=lambda item: item[1])[:10]:
                st.write(
                    f"**{sale.get('description', 'Venta')}** · {format_money(_number(sale.get('total')))} · Margen {margin:,.1f}%"
                )

    st.markdown("### Próximas acciones sugeridas")
    recommendations: list[str] = []
    if overdue:
        recommendations.append("Contacta primero a los clientes con saldos mayores y más de 30 días de antigüedad.")
    if inactive:
        recommendations.append("Reactiva clientes de alto valor con una oferta sencilla o un recordatorio de servicios disponibles.")
    if low_margin:
        recommendations.append("Revisa precios, costos y descuentos de las ventas con margen inferior a 30%.")
    if forecast_revenue < revenue * 1.05 and current_month_selected and elapsed_days < total_days:
        recommendations.append("El ritmo actual es estable; crea acciones comerciales concretas para acelerar el cierre del mes.")
    if not recommendations:
        recommendations.append("El panel no detecta riesgos comerciales prioritarios adicionales en este momento.")
    for recommendation in recommendations:
        st.info(recommendation)

    render_info_card(
        "Inteligencia comercial",
        "El pronóstico, la antigüedad de cobros, la inactividad y el margen se recalculan con los datos disponibles en la sesión.",
        "DECISIONES COMERCIALES",
    )
