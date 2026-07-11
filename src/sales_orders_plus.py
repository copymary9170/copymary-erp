"""Seguimiento operativo de ventas y pedidos."""

from collections import Counter
from datetime import date

import streamlit as st

from src import commercial as base
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save

ORDER_STATUSES = ("Pendiente", "En proceso", "Listo", "Entregado", "Cancelado")
PAYMENT_STATUSES = ("Pendiente", "Abono", "Pagado")
PRIORITIES = ("Baja", "Normal", "Alta", "Urgente")
DELIVERY_METHODS = ("Retiro", "Delivery", "Envío", "Digital", "Otro")


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _balance(sale: dict, payments: list[dict]) -> float:
    total = _num(sale.get("total"))
    paid = sum(
        _num(item.get("amount"))
        for item in payments
        if str(item.get("sale_id", "")) == str(sale.get("sale_id", "")) and not item.get("reversed")
    )
    if paid <= 0 and sale.get("payment_status") == "Pagado":
        paid = total
    return max(total - paid, 0.0)


def _update_sale(sale_id: str, updates: dict) -> None:
    sales = _rows("sales_registry")
    for sale in sales:
        if str(sale.get("sale_id", "")) == sale_id:
            sale.update(updates)
            sale["updated_at_utc"] = _now()
    _save("sales_registry", sales)


def render_sales_orders_plus() -> None:
    render_page_header("Ventas y pedidos", "Controla pagos, producción, responsables y fechas de entrega.")
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_sales()
    finally:
        base.render_page_header = original_header

    clients = _rows("customers_registry")
    sales = _rows("sales_registry")
    payments = _rows("payment_records")
    today = date.today()
    active = [sale for sale in sales if sale.get("order_status") not in {"Entregado", "Cancelado"}]
    overdue = [sale for sale in active if _as_date(sale.get("due_date")) and _as_date(sale.get("due_date")) < today]
    due_today = [sale for sale in active if _as_date(sale.get("due_date")) == today]
    ready = [sale for sale in sales if sale.get("order_status") == "Listo"]
    balance = sum(_balance(sale, payments) for sale in sales if sale.get("order_status") != "Cancelado")

    st.divider()
    st.markdown("### Control de pedidos")
    metrics = st.columns(5)
    metrics[0].metric("Activos", str(len(active)))
    metrics[1].metric("Vencidos", str(len(overdue)))
    metrics[2].metric("Para hoy", str(len(due_today)))
    metrics[3].metric("Listos", str(len(ready)))
    metrics[4].metric("Por cobrar", format_money(balance))

    if overdue:
        st.error(f"Hay {len(overdue)} pedido(s) con fecha vencida.")
    elif due_today:
        st.warning(f"Hay {len(due_today)} pedido(s) para entregar hoy.")

    filters = st.columns(4)
    search = filters[0].text_input("Buscar", placeholder="ID, cliente o descripción", key="sales_plus_search")
    status_filter = filters[1].selectbox("Estado", ("Todos", *ORDER_STATUSES), key="sales_plus_status")
    priority_filter = filters[2].selectbox("Prioridad", ("Todas", *PRIORITIES), key="sales_plus_priority")
    timing_filter = filters[3].selectbox("Entrega", ("Todas", "Vencidos", "Hoy", "Próximos", "Sin fecha"), key="sales_plus_timing")

    query = search.strip().casefold()
    filtered = []
    for sale in sales:
        due = _as_date(sale.get("due_date"))
        text = " ".join((str(sale.get("sale_id", "")), str(sale.get("description", "")), _client_name(str(sale.get("client_id", "")), clients), str(sale.get("responsible", "")))).casefold()
        if query and query not in text:
            continue
        if status_filter != "Todos" and sale.get("order_status") != status_filter:
            continue
        if priority_filter != "Todas" and str(sale.get("priority", "Normal")) != priority_filter:
            continue
        if timing_filter == "Vencidos" and not (due and due < today and sale.get("order_status") not in {"Entregado", "Cancelado"}):
            continue
        if timing_filter == "Hoy" and due != today:
            continue
        if timing_filter == "Próximos" and not (due and due > today):
            continue
        if timing_filter == "Sin fecha" and due is not None:
            continue
        filtered.append(sale)

    counts = Counter(str(sale.get("order_status", "Pendiente")) for sale in sales)
    flow = st.columns(5)
    for index, status in enumerate(ORDER_STATUSES):
        flow[index].metric(status, str(counts.get(status, 0)))

    for sale in reversed(filtered):
        sale_id = str(sale.get("sale_id", ""))
        due = _as_date(sale.get("due_date"))
        pending = _balance(sale, payments)
        with st.container(border=True):
            header = st.columns([3, 1])
            header[0].markdown(f"### {sale.get('description', 'Pedido')}")
            header[0].caption(f"ID {sale_id} · {_client_name(str(sale.get('client_id', '')), clients)} · Responsable: {sale.get('responsible') or 'Sin asignar'}")
            header[1].metric("Prioridad", str(sale.get("priority", "Normal")))
            cards = st.columns(5)
            cards[0].metric("Total", format_money(_num(sale.get("total"))))
            cards[1].metric("Saldo", format_money(pending))
            cards[2].metric("Pago", str(sale.get("payment_status", "Pendiente")))
            cards[3].metric("Estado", str(sale.get("order_status", "Pendiente")))
            cards[4].metric("Entrega", due.isoformat() if due else "Sin fecha")
            if due and due < today and sale.get("order_status") not in {"Entregado", "Cancelado"}:
                st.error("La fecha prevista de entrega ya venció.")
            if pending > 0 and sale.get("order_status") == "Listo":
                st.warning("El pedido está listo, pero todavía tiene saldo pendiente.")

            with st.expander("Planificar pedido"):
                with st.form(f"plan_sale_{sale_id}"):
                    first = st.columns(4)
                    current_status = str(sale.get("order_status", "Pendiente"))
                    if current_status not in ORDER_STATUSES:
                        current_status = "Pendiente"
                    new_status = first[0].selectbox("Estado", ORDER_STATUSES, index=ORDER_STATUSES.index(current_status), key=f"sp_status_{sale_id}")
                    current_payment = str(sale.get("payment_status", "Pendiente"))
                    if current_payment not in PAYMENT_STATUSES:
                        current_payment = "Pendiente"
                    new_payment = first[1].selectbox("Pago", PAYMENT_STATUSES, index=PAYMENT_STATUSES.index(current_payment), key=f"sp_payment_{sale_id}")
                    priority = first[2].selectbox("Prioridad", PRIORITIES, index=PRIORITIES.index(str(sale.get("priority", "Normal"))) if str(sale.get("priority", "Normal")) in PRIORITIES else 1, key=f"sp_priority_{sale_id}")
                    delivery = first[3].selectbox("Entrega", DELIVERY_METHODS, index=DELIVERY_METHODS.index(str(sale.get("delivery_method", "Retiro"))) if str(sale.get("delivery_method", "Retiro")) in DELIVERY_METHODS else 4, key=f"sp_delivery_{sale_id}")
                    second = st.columns(3)
                    due_input = second[0].date_input("Fecha prevista", value=due or today, key=f"sp_due_{sale_id}")
                    responsible = second[1].text_input("Responsable", value=str(sale.get("responsible", "")), key=f"sp_owner_{sale_id}")
                    reference = second[2].text_input("Referencia de entrega", value=str(sale.get("delivery_reference", "")), key=f"sp_reference_{sale_id}")
                    notes = st.text_area("Instrucciones internas", value=str(sale.get("production_notes", "")), key=f"sp_notes_{sale_id}")
                    save = st.form_submit_button("Guardar planificación", type="primary", use_container_width=True)
                if save:
                    _update_sale(sale_id, {"order_status": new_status, "payment_status": new_payment, "priority": priority, "delivery_method": delivery, "due_date": due_input.isoformat(), "responsible": responsible.strip(), "delivery_reference": reference.strip(), "production_notes": notes.strip()})
                    st.rerun()

    render_info_card("Seguimiento operativo", "Fechas, prioridades, responsables e instrucciones se guardan dentro de cada pedido.", "VENTAS Y PEDIDOS")
