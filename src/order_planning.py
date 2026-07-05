"""Agenda temporal de pedidos, producción y entregas para CopyMary ERP."""

from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _records(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, items: list[dict]) -> None:
    st.session_state[key] = items


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _plan_for(sale_id: str, plans: list[dict]) -> dict:
    for plan in plans:
        if str(plan.get("sale_id", "")) == sale_id:
            return dict(plan)
    return {
        "plan_id": "",
        "sale_id": sale_id,
        "delivery_date": "",
        "priority": "Normal",
        "assigned_to": "",
        "progress": 0,
        "production_status": "Sin iniciar",
        "delivery_method": "Retiro",
        "checklist": [],
        "notes": "",
        "updated_at_utc": "",
    }


def _upsert_plan(plans: list[dict], new_plan: dict) -> list[dict]:
    result: list[dict] = []
    found = False
    for plan in plans:
        if str(plan.get("sale_id", "")) == str(new_plan.get("sale_id", "")):
            result.append(new_plan)
            found = True
        else:
            result.append(dict(plan))
    if not found:
        result.append(new_plan)
    return result


def _is_late(plan: dict, sale: dict) -> bool:
    if sale.get("order_status") in {"Entregado", "Cancelado"}:
        return False
    raw_date = str(plan.get("delivery_date", ""))
    if not raw_date:
        return False
    try:
        return date.fromisoformat(raw_date) < date.today()
    except ValueError:
        return False


def _progress_from_checklist(checklist: list[dict], manual_progress: int) -> int:
    if not checklist:
        return manual_progress
    completed = sum(1 for item in checklist if item.get("done"))
    return round((completed / len(checklist)) * 100)


def render_order_planning() -> None:
    with st.container(border=True):
        render_page_header(
            "Agenda de producción y entregas",
            "Organiza pedidos por fecha, prioridad, responsable y avance.",
        )
        st.caption("La agenda se conecta con Ventas y pedidos y se incluye en el Respaldo general.")

    sales = _records("sales_registry")
    clients = _records("customers_registry")
    products = _records("products_registry")
    plans = _records("order_plans")

    active_sales = [sale for sale in sales if sale.get("order_status") != "Cancelado"]
    late_count = sum(1 for sale in active_sales if _is_late(_plan_for(str(sale.get("sale_id", "")), plans), sale))
    due_today = sum(
        1
        for sale in active_sales
        if _plan_for(str(sale.get("sale_id", "")), plans).get("delivery_date") == date.today().isoformat()
        and sale.get("order_status") != "Entregado"
    )
    ready_count = sum(1 for sale in active_sales if sale.get("order_status") == "Listo")
    unplanned = sum(1 for sale in active_sales if not _plan_for(str(sale.get("sale_id", "")), plans).get("delivery_date"))

    metrics = st.columns(4)
    metrics[0].metric("Pedidos activos", str(len(active_sales)))
    metrics[1].metric("Atrasados", str(late_count))
    metrics[2].metric("Entregas hoy", str(due_today))
    metrics[3].metric("Sin planificar", str(unplanned))

    st.subheader("Planificar pedido")
    if not active_sales:
        st.info("No hay ventas o pedidos activos para planificar.")
    else:
        sale_options = {
            f"{sale.get('description', 'Pedido')} · {_client_name(str(sale.get('client_id', '')), clients)} · ID {sale.get('sale_id', '')}": sale
            for sale in active_sales
        }
        selected_label = st.selectbox("Pedido", tuple(sale_options.keys()))
        selected_sale = sale_options[selected_label]
        sale_id = str(selected_sale.get("sale_id", ""))
        current_plan = _plan_for(sale_id, plans)

        with st.form("order_plan_form"):
            row1 = st.columns(4)
            with row1[0]:
                current_date = None
                if current_plan.get("delivery_date"):
                    try:
                        current_date = date.fromisoformat(str(current_plan.get("delivery_date")))
                    except ValueError:
                        current_date = None
                delivery_date = st.date_input("Fecha de entrega", value=current_date)
            with row1[1]:
                priority = st.selectbox(
                    "Prioridad",
                    ("Baja", "Normal", "Alta", "Urgente"),
                    index=("Baja", "Normal", "Alta", "Urgente").index(str(current_plan.get("priority", "Normal"))),
                )
            with row1[2]:
                assigned_to = st.text_input("Responsable", value=str(current_plan.get("assigned_to", "")), max_chars=80)
            with row1[3]:
                delivery_method = st.selectbox(
                    "Entrega",
                    ("Retiro", "Delivery", "Envío", "Digital", "Otro"),
                    index=("Retiro", "Delivery", "Envío", "Digital", "Otro").index(str(current_plan.get("delivery_method", "Retiro"))),
                )

            row2 = st.columns(2)
            with row2[0]:
                production_status = st.selectbox(
                    "Estado de producción",
                    ("Sin iniciar", "Diseño", "Producción", "Revisión", "Listo", "Entregado"),
                    index=("Sin iniciar", "Diseño", "Producción", "Revisión", "Listo", "Entregado").index(str(current_plan.get("production_status", "Sin iniciar"))),
                )
            with row2[1]:
                progress = st.slider("Avance manual", min_value=0, max_value=100, value=int(current_plan.get("progress", 0)), step=5)

            checklist: list[dict] = []
            st.markdown("#### Checklist")
            old_checklist = [dict(item) for item in current_plan.get("checklist", []) if isinstance(item, dict)]
            for index in range(4):
                previous = old_checklist[index] if index < len(old_checklist) else {"label": "", "done": False}
                columns = st.columns([3, 1])
                with columns[0]:
                    label = st.text_input(
                        f"Paso {index + 1}",
                        value=str(previous.get("label", "")),
                        key=f"plan_step_{sale_id}_{index}",
                        max_chars=120,
                    )
                with columns[1]:
                    done = st.checkbox(
                        "Completado",
                        value=bool(previous.get("done", False)),
                        key=f"plan_done_{sale_id}_{index}",
                    )
                if label.strip():
                    checklist.append({"label": label.strip(), "done": done})

            notes = st.text_area("Notas operativas", value=str(current_plan.get("notes", "")), max_chars=400)
            submitted = st.form_submit_button("Guardar planificación", type="primary", use_container_width=True)

        if submitted:
            computed_progress = _progress_from_checklist(checklist, int(progress))
            new_plan = {
                "plan_id": current_plan.get("plan_id") or uuid4().hex[:10],
                "sale_id": sale_id,
                "delivery_date": delivery_date.isoformat() if delivery_date else "",
                "priority": priority,
                "assigned_to": assigned_to.strip(),
                "progress": computed_progress,
                "production_status": production_status,
                "delivery_method": delivery_method,
                "checklist": checklist,
                "notes": notes.strip(),
                "updated_at_utc": _now(),
            }
            _save("order_plans", _upsert_plan(plans, new_plan))

            updated_sales: list[dict] = []
            for sale in sales:
                updated = dict(sale)
                if str(sale.get("sale_id", "")) == sale_id:
                    if production_status == "Listo":
                        updated["order_status"] = "Listo"
                    elif production_status == "Entregado":
                        updated["order_status"] = "Entregado"
                    elif production_status in {"Diseño", "Producción", "Revisión"}:
                        updated["order_status"] = "En proceso"
                updated_sales.append(updated)
            _save("sales_registry", updated_sales)
            st.success("Planificación guardada.")
            st.rerun()

    st.divider()
    st.subheader("Agenda")
    filter_columns = st.columns(3)
    with filter_columns[0]:
        priority_filter = st.selectbox("Prioridad", ("Todas", "Baja", "Normal", "Alta", "Urgente"))
    with filter_columns[1]:
        status_filter = st.selectbox("Producción", ("Todos", "Sin iniciar", "Diseño", "Producción", "Revisión", "Listo", "Entregado"))
    with filter_columns[2]:
        timing_filter = st.selectbox("Plazo", ("Todos", "Atrasados", "Hoy", "Próximos", "Sin fecha"))

    agenda: list[tuple[dict, dict]] = []
    for sale in active_sales:
        plan = _plan_for(str(sale.get("sale_id", "")), plans)
        if priority_filter != "Todas" and plan.get("priority") != priority_filter:
            continue
        if status_filter != "Todos" and plan.get("production_status") != status_filter:
            continue
        raw_date = str(plan.get("delivery_date", ""))
        if timing_filter == "Atrasados" and not _is_late(plan, sale):
            continue
        if timing_filter == "Hoy" and raw_date != date.today().isoformat():
            continue
        if timing_filter == "Próximos":
            try:
                if not raw_date or date.fromisoformat(raw_date) <= date.today():
                    continue
            except ValueError:
                continue
        if timing_filter == "Sin fecha" and raw_date:
            continue
        agenda.append((sale, plan))

    agenda.sort(key=lambda pair: (pair[1].get("delivery_date") or "9999-12-31", -int(pair[1].get("progress", 0))))

    if not agenda:
        st.info("No hay pedidos que coincidan con los filtros.")
        return

    for sale, plan in agenda:
        late = _is_late(plan, sale)
        with st.container(border=True):
            st.markdown(f"### {sale.get('description', 'Pedido')}")
            st.caption(
                f"{_client_name(str(sale.get('client_id', '')), clients)} · ID {sale.get('sale_id', '')} · "
                f"Entrega {plan.get('delivery_date') or 'Sin fecha'}"
            )
            columns = st.columns(5)
            columns[0].metric("Total", format_money(float(sale.get("total", 0.0))))
            columns[1].metric("Prioridad", str(plan.get("priority", "Normal")))
            columns[2].metric("Responsable", str(plan.get("assigned_to") or "Sin asignar"))
            columns[3].metric("Avance", f"{int(plan.get('progress', 0))}%")
            columns[4].metric("Plazo", "ATRASADO" if late else str(plan.get("production_status", "Sin iniciar")))
            st.progress(int(plan.get("progress", 0)) / 100)

            checklist = [dict(item) for item in plan.get("checklist", []) if isinstance(item, dict)]
            if checklist:
                st.markdown("**Checklist:**")
                for item in checklist:
                    mark = "✅" if item.get("done") else "⬜"
                    st.write(f"{mark} {item.get('label', '')}")

            render_info_card(
                "Entrega",
                f"Método: {plan.get('delivery_method', 'Retiro')}. Notas: {plan.get('notes') or 'Sin notas'}.",
                "AGENDA OPERATIVA",
            )

    if products:
        st.caption(f"El catálogo tiene {len(products)} producto(s) o servicio(s) disponibles para planificación futura.")
