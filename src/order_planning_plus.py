"""Agenda ampliada de producción y entregas."""

from collections import Counter, defaultdict
from datetime import date, timedelta
import csv
import io

import streamlit as st

from src import order_planning as base
from src.components import render_info_card, render_page_header
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


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


def _plan_for(sale_id: str, plans: list[dict]) -> dict:
    for plan in plans:
        if str(plan.get("sale_id", "")) == sale_id:
            return dict(plan)
    return {}


def _delivery_date(sale: dict, plan: dict) -> date | None:
    return _as_date(plan.get("delivery_date") or sale.get("due_date"))


def _export(sales: list[dict], plans: list[dict], clients: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Pedido", "Cliente", "Entrega", "Prioridad", "Responsable", "Producción", "Avance"])
    for sale in sales:
        plan = _plan_for(str(sale.get("sale_id", "")), plans)
        delivery = _delivery_date(sale, plan)
        writer.writerow([
            sale.get("sale_id", ""),
            _client_name(str(sale.get("client_id", "")), clients),
            delivery.isoformat() if delivery else "",
            plan.get("priority", sale.get("priority", "Normal")),
            plan.get("assigned_to", sale.get("responsible", "")),
            plan.get("production_status", "Sin iniciar"),
            plan.get("progress", 0),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_order_planning_plus() -> None:
    render_page_header("Agenda de producción y entregas", "Controla carga, atrasos, responsables y entregas próximas.")
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_order_planning()
    finally:
        base.render_page_header = original_header

    sales = [sale for sale in _rows("sales_registry") if sale.get("order_status") not in {"Cancelado", "Entregado"}]
    plans = _rows("order_plans")
    clients = _rows("customers_registry")
    today = date.today()
    scheduled = [(sale, _plan_for(str(sale.get("sale_id", "")), plans)) for sale in sales]

    late = [item for item in scheduled if _delivery_date(*item) and _delivery_date(*item) < today]
    due_today = [item for item in scheduled if _delivery_date(*item) == today]
    next_week = [item for item in scheduled if _delivery_date(*item) and today < _delivery_date(*item) <= today + timedelta(days=7)]
    no_date = [item for item in scheduled if _delivery_date(*item) is None]

    st.divider()
    metrics = st.columns(5)
    metrics[0].metric("Activos", str(len(sales)))
    metrics[1].metric("Atrasados", str(len(late)))
    metrics[2].metric("Para hoy", str(len(due_today)))
    metrics[3].metric("Próximos 7 días", str(len(next_week)))
    metrics[4].metric("Sin fecha", str(len(no_date)))

    if late:
        st.error(f"Hay {len(late)} pedido(s) atrasado(s).")
    if no_date:
        st.warning(f"Hay {len(no_date)} pedido(s) sin fecha de entrega.")

    st.markdown("### Carga por responsable")
    workload: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "late": 0})
    for sale, plan in scheduled:
        owner = str(plan.get("assigned_to") or sale.get("responsible") or "Sin asignar")
        workload[owner]["total"] += 1
        delivery = _delivery_date(sale, plan)
        if delivery and delivery < today:
            workload[owner]["late"] += 1
    for owner, values in sorted(workload.items(), key=lambda item: item[1]["total"], reverse=True):
        columns = st.columns([3, 1, 1])
        columns[0].markdown(f"**{owner}**")
        columns[1].metric("Pedidos", str(values["total"]))
        columns[2].metric("Atrasados", str(values["late"]))

    st.markdown("### Próximos 7 días")
    for offset in range(8):
        day = today + timedelta(days=offset)
        items = [(sale, plan) for sale, plan in scheduled if _delivery_date(sale, plan) == day]
        with st.expander(f"{day.isoformat()} · {len(items)} pedido(s)", expanded=offset == 0):
            if not items:
                st.caption("Sin entregas programadas.")
            for sale, plan in items:
                st.write(f"**{sale.get('description', 'Pedido')}** · {_client_name(str(sale.get('client_id', '')), clients)} · {plan.get('assigned_to') or sale.get('responsible') or 'Sin asignar'} · {int(plan.get('progress', 0))}%")

    st.markdown("### Conflictos de capacidad")
    load = Counter(_delivery_date(sale, plan).isoformat() for sale, plan in scheduled if _delivery_date(sale, plan))
    overloaded = {day: count for day, count in load.items() if count >= 5}
    if overloaded:
        for day, count in sorted(overloaded.items()):
            st.warning(f"{day}: {count} pedidos programados.")
    else:
        st.success("No hay días con 5 o más pedidos programados.")

    unsynced = [sale for sale in sales if not _plan_for(str(sale.get("sale_id", "")), plans) and sale.get("due_date")]
    if unsynced and st.button("Sincronizar pedidos con fecha", use_container_width=True, type="primary"):
        updated = list(plans)
        for sale in unsynced:
            updated.append({
                "plan_id": f"auto-{sale.get('sale_id', '')}",
                "sale_id": str(sale.get("sale_id", "")),
                "delivery_date": str(sale.get("due_date", "")),
                "priority": str(sale.get("priority", "Normal")),
                "assigned_to": str(sale.get("responsible", "")),
                "progress": 0,
                "production_status": "Sin iniciar",
                "delivery_method": str(sale.get("delivery_method", "Retiro")),
                "checklist": [],
                "notes": "Creado desde Ventas y pedidos.",
                "updated_at_utc": _now(),
            })
        _save("order_plans", updated)
        st.rerun()

    st.download_button("Descargar agenda CSV", _export(sales, plans, clients), f"agenda_{today.isoformat()}.csv", "text/csv", use_container_width=True)
    render_info_card("Agenda ampliada", "La carga, los conflictos y las entregas se calculan con los pedidos de la sesión.", "PRODUCCIÓN Y ENTREGAS")
