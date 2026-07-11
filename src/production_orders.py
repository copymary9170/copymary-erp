"""Órdenes de producción para CopyMary ERP.

Primera pieza del motor de producción: crea OP, controla estados,
prioridades, responsables, tiempos, calidad básica y trazabilidad inicial.
"""

from datetime import date
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


STATUSES = (
    "Pendiente",
    "Aprobada",
    "En producción",
    "En pausa",
    "Finalizada",
    "Entregada",
    "Cancelada",
)

PRIORITIES = ("Alta", "Media", "Baja")

STATUS_FLOW = {
    "Pendiente": ("Aprobada", "Cancelada"),
    "Aprobada": ("En producción", "Cancelada"),
    "En producción": ("En pausa", "Finalizada", "Cancelada"),
    "En pausa": ("En producción", "Cancelada"),
    "Finalizada": ("Entregada",),
    "Entregada": (),
    "Cancelada": (),
}


def _activate_backup() -> None:
    for section, label in (
        ("production_orders", "Órdenes de producción"),
        ("production_order_events", "Eventos de órdenes de producción"),
        ("production_quality_checks", "Control de calidad de producción"),
        ("production_time_logs", "Tiempos reales de producción"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _recipe_options() -> dict[str, dict]:
    recipes = [dict(row) for row in st.session_state.get("product_recipes", []) if isinstance(row, dict)]
    options = {"Sin receta vinculada": {"recipe_id": "", "name": "Sin receta"}}
    for recipe in recipes:
        options[f"{recipe.get('name', 'Receta')} · {recipe.get('recipe_id', '')}"] = recipe
    return options


def _add_event(order_id: str, action: str, responsible: str, note: str = "") -> None:
    events = _rows("production_order_events")
    events.append({
        "event_id": f"OPE-{uuid4().hex[:8].upper()}",
        "order_id": order_id,
        "action": action,
        "responsible": responsible.strip() or "Sistema",
        "note": note.strip(),
        "created_at_utc": _now(),
    })
    _save("production_order_events", events)


def _order_cost(order: dict) -> float:
    return _num(order.get("estimated_unit_cost")) * _num(order.get("quantity"), 1.0)


def _order_price(order: dict) -> float:
    return _num(order.get("estimated_unit_price")) * _num(order.get("quantity"), 1.0)


def _open_orders(orders: list[dict]) -> list[dict]:
    return [row for row in orders if row.get("status") not in {"Entregada", "Cancelada"}]


def _late_orders(orders: list[dict]) -> list[dict]:
    today = date.today().isoformat()
    return [row for row in _open_orders(orders) if str(row.get("due_date", "")) < today]


def _export_orders(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["OP", "Producto", "Cliente", "Cantidad", "Estado", "Prioridad", "Responsable", "Entrega", "Costo estimado", "Precio estimado"])
    for row in rows:
        writer.writerow([
            row.get("order_id", ""), row.get("product_name", ""), row.get("customer_name", ""), row.get("quantity", 0),
            row.get("status", ""), row.get("priority", ""), row.get("responsible", ""), row.get("due_date", ""),
            _order_cost(row), _order_price(row),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_production_orders() -> None:
    render_page_header("Órdenes de producción", "Crea, aprueba, ejecuta, pausa, finaliza y entrega trabajos productivos.")

    orders = _rows("production_orders")
    events = _rows("production_order_events")
    checks = _rows("production_quality_checks")
    time_logs = _rows("production_time_logs")
    open_orders = _open_orders(orders)
    late_orders = _late_orders(orders)
    in_process = [row for row in orders if row.get("status") == "En producción"]

    metrics = st.columns(5)
    metrics[0].metric("Órdenes abiertas", str(len(open_orders)))
    metrics[1].metric("En producción", str(len(in_process)))
    metrics[2].metric("Atrasadas", str(len(late_orders)))
    metrics[3].metric("Costo estimado", format_money(sum(_order_cost(row) for row in open_orders), get_currency()))
    metrics[4].metric("Precio estimado", format_money(sum(_order_price(row) for row in open_orders), get_currency()))

    if late_orders:
        st.error("Hay órdenes de producción atrasadas.")

    create_tab, board_tab, time_tab, quality_tab, trace_tab = st.tabs(("Crear OP", "Tablero", "Tiempos", "Calidad", "Trazabilidad"))

    with create_tab:
        recipes = _recipe_options()
        with st.form("production_order_form", clear_on_submit=True):
            selected_recipe = st.selectbox("Receta / BOM", tuple(recipes.keys()))
            product_name = st.text_input("Producto", value="")
            customer_name = st.text_input("Cliente")
            quantity = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
            priority = st.selectbox("Prioridad", PRIORITIES)
            responsible = st.text_input("Responsable")
            due_date = st.date_input("Fecha compromiso", value=date.today())
            estimated_unit_cost = st.number_input("Costo estimado unitario", min_value=0.0, value=0.0, step=1.0)
            estimated_unit_price = st.number_input("Precio estimado unitario", min_value=0.0, value=0.0, step=1.0)
            notes = st.text_area("Instrucciones", max_chars=800)
            submitted = st.form_submit_button("Crear orden", type="primary", use_container_width=True)
        if submitted:
            recipe = recipes[selected_recipe]
            final_product = product_name.strip() or str(recipe.get("name", "Trabajo productivo"))
            if not final_product or not responsible.strip():
                st.error("Producto y responsable son obligatorios.")
            else:
                order_id = f"OP-{uuid4().hex[:8].upper()}"
                orders.append({
                    "order_id": order_id,
                    "recipe_id": str(recipe.get("recipe_id", "")),
                    "product_name": final_product,
                    "customer_name": customer_name.strip(),
                    "quantity": float(quantity),
                    "priority": priority,
                    "responsible": responsible.strip(),
                    "due_date": due_date.isoformat(),
                    "estimated_unit_cost": float(estimated_unit_cost),
                    "estimated_unit_price": float(estimated_unit_price),
                    "notes": notes.strip(),
                    "status": "Pendiente",
                    "created_at_utc": _now(),
                })
                _save("production_orders", orders)
                _add_event(order_id, "Orden creada", responsible, notes)
                st.rerun()
        st.download_button("Descargar OP CSV", data=_export_orders(orders), file_name="ordenes_produccion.csv", mime="text/csv", use_container_width=True, disabled=not orders)

    with board_tab:
        status_filter = st.selectbox("Estado", ("Todos", *STATUSES))
        filtered = [row for row in orders if status_filter == "Todos" or row.get("status") == status_filter]
        if not filtered:
            st.info("No hay órdenes con este filtro.")
        for order in filtered[:150]:
            status = str(order.get("status", "Pendiente"))
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{order.get('order_id')} · {order.get('product_name')}**")
                cols[0].caption(f"Cliente: {order.get('customer_name') or 'Sin cliente'} · Responsable: {order.get('responsible')} · Entrega: {order.get('due_date')}")
                cols[1].metric("Estado", status)
                cols[2].metric("Cantidad", str(order.get("quantity", 0)))
                cols[3].metric("Prioridad", str(order.get("priority", "")))
                next_statuses = STATUS_FLOW.get(status, ())
                if next_statuses:
                    with st.form(f"change_status_{order.get('order_id')}"):
                        new_status = st.selectbox("Mover a", next_statuses, key=f"next_{order.get('order_id')}")
                        responsible = st.text_input("Responsable del cambio", value=str(order.get("responsible", "")), key=f"resp_{order.get('order_id')}")
                        note = st.text_input("Nota", key=f"note_{order.get('order_id')}")
                        submitted = st.form_submit_button("Actualizar estado", type="primary", use_container_width=True)
                    if submitted:
                        changed = []
                        for row in orders:
                            current = dict(row)
                            if current.get("order_id") == order.get("order_id"):
                                current["status"] = new_status
                                current["updated_at_utc"] = _now()
                                if new_status == "En producción" and not current.get("started_at_utc"):
                                    current["started_at_utc"] = _now()
                                if new_status == "Finalizada":
                                    current["finished_at_utc"] = _now()
                                if new_status == "Entregada":
                                    current["delivered_at_utc"] = _now()
                                if new_status == "Cancelada":
                                    current["cancelled_at_utc"] = _now()
                            changed.append(current)
                        _save("production_orders", changed)
                        _add_event(str(order.get("order_id", "")), f"Estado cambiado a {new_status}", responsible, note)
                        st.rerun()

    with time_tab:
        active_options = {f"{row.get('order_id')} · {row.get('product_name')}": row for row in orders if row.get("status") in {"En producción", "En pausa", "Finalizada"}}
        if not active_options:
            st.info("No hay órdenes activas para registrar tiempos.")
        else:
            with st.form("production_time_log_form", clear_on_submit=True):
                selected = st.selectbox("Orden", tuple(active_options.keys()))
                process = st.text_input("Proceso", placeholder="Impresión, corte, armado...")
                minutes = st.number_input("Minutos reales", min_value=0.0, value=0.0, step=5.0)
                responsible = st.text_input("Responsable")
                note = st.text_input("Nota")
                submitted = st.form_submit_button("Registrar tiempo", type="primary", use_container_width=True)
            if submitted:
                if not process.strip() or minutes <= 0 or not responsible.strip():
                    st.error("Proceso, minutos y responsable son obligatorios.")
                else:
                    order = active_options[selected]
                    time_logs.append({
                        "time_id": f"OPT-{uuid4().hex[:8].upper()}",
                        "order_id": order.get("order_id"),
                        "process": process.strip(),
                        "minutes": float(minutes),
                        "responsible": responsible.strip(),
                        "note": note.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("production_time_logs", time_logs)
                    _add_event(str(order.get("order_id", "")), f"Tiempo registrado: {process}", responsible, f"{minutes} min. {note}")
                    st.rerun()
        for row in reversed(time_logs[-100:]):
            st.write(f"**{row.get('order_id')} · {row.get('process')}** · {row.get('minutes')} min · {row.get('responsible')} — {row.get('note', '')}")

    with quality_tab:
        finished_options = {f"{row.get('order_id')} · {row.get('product_name')}": row for row in orders if row.get("status") in {"En producción", "Finalizada", "Entregada"}}
        if not finished_options:
            st.info("No hay órdenes para control de calidad.")
        else:
            with st.form("production_quality_form", clear_on_submit=True):
                selected = st.selectbox("Orden", tuple(finished_options.keys()))
                result = st.selectbox("Resultado", ("Aprobado", "Aprobado con observaciones", "Requiere reproceso", "Rechazado"))
                reviewer = st.text_input("Revisado por")
                defects = st.number_input("Unidades con defecto", min_value=0.0, value=0.0, step=1.0)
                note = st.text_area("Observación", max_chars=700)
                submitted = st.form_submit_button("Guardar calidad", type="primary", use_container_width=True)
            if submitted:
                if not reviewer.strip():
                    st.error("Revisor obligatorio.")
                else:
                    order = finished_options[selected]
                    checks.append({
                        "check_id": f"QC-{uuid4().hex[:8].upper()}",
                        "order_id": order.get("order_id"),
                        "result": result,
                        "reviewer": reviewer.strip(),
                        "defects": float(defects),
                        "note": note.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("production_quality_checks", checks)
                    _add_event(str(order.get("order_id", "")), f"Calidad: {result}", reviewer, note)
                    st.rerun()
        for row in reversed(checks[-100:]):
            st.write(f"**{row.get('order_id')} · {row.get('result')}** · defectos {row.get('defects')} · {row.get('reviewer')} — {row.get('note', '')}")

    with trace_tab:
        order_options = {f"{row.get('order_id')} · {row.get('product_name')}": row for row in orders}
        if not order_options:
            st.info("No hay órdenes para consultar.")
        else:
            selected = st.selectbox("Orden", tuple(order_options.keys()))
            order = order_options[selected]
            st.markdown(f"### {order.get('order_id')} · {order.get('product_name')}")
            st.caption(f"Estado {order.get('status')} · prioridad {order.get('priority')} · entrega {order.get('due_date')}")
            st.write(order.get("notes", ""))
            st.markdown("#### Línea de tiempo")
            for event in [row for row in events if row.get("order_id") == order.get("order_id")][-200:]:
                st.write(f"**{event.get('action')}** · {event.get('responsible')} · {event.get('created_at_utc')} — {event.get('note', '')}")
            st.markdown("#### Tiempos")
            total_minutes = sum(_num(row.get("minutes")) for row in time_logs if row.get("order_id") == order.get("order_id"))
            st.metric("Minutos reales", f"{total_minutes:,.1f}")
            st.markdown("#### Calidad")
            for check in [row for row in checks if row.get("order_id") == order.get("order_id")][-50:]:
                st.write(f"{check.get('result')} · {check.get('reviewer')} · defectos {check.get('defects')}")

    render_info_card("Base de producción", "Esta fase crea la orden de producción y su trazabilidad. Las siguientes fases conectan BOM multinivel, reserva/consumo de inventario y costo real.", "FASE 3")


app_shell.FUNCTIONAL_MODULES["Órdenes de producción"] = render_production_orders
