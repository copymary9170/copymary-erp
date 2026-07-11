"""Workflow avanzado de reversos de producción."""

from collections import Counter, defaultdict

from uuid import uuid4

import streamlit as st

from src import session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("production_reversal_requests", "Solicitudes de reverso de producción"),
        ("production_reversal_events", "Eventos de reverso de producción"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = (
        "general_settings",
        *session_backup.LIST_SECTIONS,
        *session_backup.DICT_SECTIONS,
    )


_activate_backup()

STATUSES = ("Pendiente", "Aprobado", "Rechazado", "Ejecutado")
DESTINATIONS = ("Regresar inventario", "Merma", "Reciclaje", "Retrabajo", "Destrucción")


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _recipe(production: dict, products: list[dict]) -> list[dict]:
    snapshot = [dict(item) for item in production.get("recipe_snapshot", []) if isinstance(item, dict)]
    if snapshot:
        return _consolidate(snapshot)
    product_id = str(production.get("product_id", ""))
    product = next((item for item in products if str(item.get("product_id", "")) == product_id), {})
    return _consolidate([dict(item) for item in product.get("recipe", []) if isinstance(item, dict)])


def _consolidate(recipe: list[dict]) -> list[dict]:
    totals: dict[str, float] = defaultdict(float)
    for component in recipe:
        item_id = str(component.get("item_id", "")).strip()
        qty = _num(component.get("quantity"))
        if item_id and qty > 0:
            totals[item_id] += qty
    return [{"item_id": item_id, "quantity": qty} for item_id, qty in totals.items()]


def _item_name(item_id: str, inventory: list[dict]) -> str:
    for item in inventory:
        if str(item.get("item_id", "")) == item_id:
            return str(item.get("name", "Material"))
    return "Material no disponible"


def _request_for(request_id: str, requests: list[dict]) -> dict:
    return next((item for item in requests if str(item.get("request_id", "")) == request_id), {})


def _add_event(request_id: str, event_type: str, note: str, responsible: str = "") -> None:
    events = _rows("production_reversal_events")
    events.append({
        "event_id": uuid4().hex[:12],
        "request_id": request_id,
        "event_type": event_type,
        "note": note.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("production_reversal_events", events)


def _update_request(request_id: str, updates: dict) -> None:
    requests = _rows("production_reversal_requests")
    changed = []
    for request in requests:
        row = dict(request)
        if str(row.get("request_id", "")) == request_id:
            row.update(updates)
            row["updated_at_utc"] = _now()
        changed.append(row)
    _save("production_reversal_requests", changed)


def _already_requested(production_id: str, requests: list[dict]) -> float:
    return sum(
        _num(item.get("quantity"))
        for item in requests
        if str(item.get("production_id", "")) == production_id and str(item.get("status", "")) in {"Pendiente", "Aprobado", "Ejecutado"}
    )


def _simulate(production: dict, request: dict, products: list[dict], inventory: list[dict]) -> list[dict]:
    ratio_quantity = _num(request.get("quantity"))
    component_policy = request.get("components", {}) if isinstance(request.get("components"), dict) else {}
    rows = []
    for component in _recipe(production, products):
        item_id = str(component.get("item_id", ""))
        per_unit = _num(component.get("quantity"))
        selected = component_policy.get(item_id, {}) if isinstance(component_policy.get(item_id), dict) else {}
        enabled = bool(selected.get("enabled", True))
        destination = str(selected.get("destination", request.get("destination", "Regresar inventario")))
        quantity = per_unit * ratio_quantity if enabled else 0.0
        inventory_item = next((item for item in inventory if str(item.get("item_id", "")) == item_id), {})
        purchased = max(_num(inventory_item.get("purchased_quantity"), 1.0), 0.01)
        unit_cost = _num(inventory_item.get("purchase_cost")) / purchased
        recoverable = quantity if destination == "Regresar inventario" else 0.0
        lost = quantity if destination != "Regresar inventario" else 0.0
        rows.append({
            "item_id": item_id,
            "name": _item_name(item_id, inventory),
            "quantity": quantity,
            "recoverable": recoverable,
            "lost": lost,
            "destination": destination,
            "unit_cost": unit_cost,
            "cost": unit_cost * quantity,
        })
    return rows


def _execute_request(request: dict, production: dict, products: list[dict], inventory: list[dict], movements: list[dict], stock: list[dict]) -> None:
    simulation = _simulate(production, request, products, inventory)
    production_id = str(production.get("production_id", ""))
    request_id = str(request.get("request_id", ""))
    quantity = _num(request.get("quantity"))
    product_id = str(production.get("product_id", ""))
    variant_id = str(production.get("variant_id", ""))

    updated_inventory = []
    for item in inventory:
        row = dict(item)
        item_id = str(row.get("item_id", ""))
        returned = sum(line["recoverable"] for line in simulation if line["item_id"] == item_id)
        if returned > 0:
            previous = _num(row.get("available_quantity"))
            row["available_quantity"] = previous + returned
            movements.append({
                "movement_id": uuid4().hex[:10],
                "created_at_utc": _now(),
                "item_id": item_id,
                "item_name": str(row.get("name", "Material")),
                "movement_type": "Entrada",
                "quantity": returned,
                "unit_name": str(row.get("unit_name", "unidad")),
                "reason": f"Reverso aprobado {request_id}",
                "previous_quantity": previous,
                "resulting_quantity": previous + returned,
            })
        updated_inventory.append(row)

    updated_stock = []
    reduced = False
    for item in stock:
        row = dict(item)
        if str(row.get("product_id", "")) == product_id and str(row.get("variant_id", "")) == variant_id and not reduced:
            row["quantity"] = max(_num(row.get("quantity")) - quantity, 0.0)
            row["updated_at_utc"] = _now()
            reduced = True
        updated_stock.append(row)

    updated_log = []
    for item in _rows("production_log"):
        row = dict(item)
        if str(row.get("production_id", "")) == production_id:
            reversed_qty = _num(row.get("reversed_quantity")) + quantity
            row["reversed_quantity"] = reversed_qty
            row["reversal_status"] = "Parcial" if reversed_qty < _num(row.get("quantity")) else "Completo"
            row["reversed"] = reversed_qty >= _num(row.get("quantity"))
            row["last_reversal_request_id"] = request_id
            row["updated_at_utc"] = _now()
        updated_log.append(row)

    _save("inventory_registry", updated_inventory)
    _save("inventory_movements", movements)
    _save("finished_goods_stock", updated_stock)
    _save("production_log", updated_log)
    _update_request(request_id, {
        "status": "Ejecutado",
        "executed_at_utc": _now(),
        "simulation_snapshot": simulation,
        "recovered_cost": sum(line["unit_cost"] * line["recoverable"] for line in simulation),
        "lost_cost": sum(line["unit_cost"] * line["lost"] for line in simulation),
    })
    _add_event(request_id, "Reverso ejecutado", "Inventario y producción actualizados", str(request.get("approved_by", "")))


def render_production_reversals() -> None:
    render_page_header(
        "Reversos de producción",
        "Solicita, simula, aprueba y ejecuta reversos completos o parciales con trazabilidad.",
    )

    productions = [item for item in _rows("production_log") if not item.get("reversed")]
    products = _rows("products_registry")
    inventory = _rows("inventory_registry")
    movements = _rows("inventory_movements")
    stock = _rows("finished_goods_stock")
    requests = _rows("production_reversal_requests")
    events = _rows("production_reversal_events")

    counts = Counter(str(item.get("status", "Pendiente")) for item in requests)
    recovered = sum(_num(item.get("recovered_cost")) for item in requests if item.get("status") == "Ejecutado")
    lost = sum(_num(item.get("lost_cost")) for item in requests if item.get("status") == "Ejecutado")

    metrics = st.columns(5)
    metrics[0].metric("Pendientes", str(counts.get("Pendiente", 0)))
    metrics[1].metric("Aprobados", str(counts.get("Aprobado", 0)))
    metrics[2].metric("Ejecutados", str(counts.get("Ejecutado", 0)))
    metrics[3].metric("Costo recuperado", format_money(recovered))
    metrics[4].metric("Costo perdido", format_money(lost))

    request_tab, approval_tab, execute_tab, dashboard_tab, history_tab = st.tabs(
        ("Solicitud", "Aprobación", "Ejecución", "Indicadores", "Historial")
    )

    with request_tab:
        if not productions:
            st.info("No hay producciones vigentes disponibles para reverso.")
        else:
            options = {
                f"{item.get('product_name', 'Producción')} · {item.get('production_id', '')} · disponible {max(_num(item.get('quantity')) - _num(item.get('reversed_quantity')), 0):,.2f}": str(item.get("production_id", ""))
                for item in productions
                if max(_num(item.get("quantity")) - _num(item.get("reversed_quantity")), 0) > 0
            }
            selected = st.selectbox("Producción", tuple(options.keys()), key="reversal_request_production")
            production_id = options[selected]
            production = next(item for item in productions if str(item.get("production_id", "")) == production_id)
            available = max(_num(production.get("quantity")) - _num(production.get("reversed_quantity")) - _already_requested(production_id, requests), 0.0)
            recipe = _recipe(production, products)
            with st.form("production_reversal_request_form"):
                first = st.columns(4)
                reversal_type = first[0].selectbox("Tipo", ("Completo", "Parcial", "Por componentes", "Retrabajo"))
                quantity = first[1].number_input("Cantidad a reversar", min_value=0.0, max_value=float(available), value=float(available), step=1.0)
                destination = first[2].selectbox("Destino general", DESTINATIONS)
                priority = first[3].selectbox("Prioridad", ("Normal", "Alta", "Urgente"))
                requested_by = st.text_input("Solicitado por")
                reason = st.text_area("Motivo obligatorio", max_chars=700)
                component_choices = {}
                if reversal_type == "Por componentes":
                    st.markdown("#### Componentes a afectar")
                    for component in recipe:
                        item_id = str(component.get("item_id", ""))
                        cols = st.columns([2, 1, 1])
                        enabled = cols[0].checkbox(_item_name(item_id, inventory), value=True, key=f"component_enabled_{item_id}")
                        component_destination = cols[1].selectbox("Destino", DESTINATIONS, key=f"component_destination_{item_id}")
                        cols[2].metric("Por unidad", f"{_num(component.get('quantity')):,.2f}")
                        component_choices[item_id] = {"enabled": enabled, "destination": component_destination}
                submitted = st.form_submit_button("Crear solicitud de reverso", type="primary", use_container_width=True)
            if submitted:
                if quantity <= 0:
                    st.error("La cantidad a reversar debe ser mayor que cero.")
                elif not reason.strip():
                    st.error("El motivo del reverso es obligatorio.")
                elif quantity > available:
                    st.error("La cantidad solicitada supera la cantidad disponible sin reversar.")
                else:
                    request_id = f"REV-{uuid4().hex[:8].upper()}"
                    request = {
                        "request_id": request_id,
                        "production_id": production_id,
                        "product_id": str(production.get("product_id", "")),
                        "product_name": str(production.get("product_name", "Producción")),
                        "reversal_type": reversal_type,
                        "quantity": float(quantity),
                        "destination": destination,
                        "priority": priority,
                        "reason": reason.strip(),
                        "requested_by": requested_by.strip() or "Sin asignar",
                        "components": component_choices,
                        "status": "Pendiente",
                        "created_at_utc": _now(),
                    }
                    requests.append(request)
                    _save("production_reversal_requests", requests)
                    _add_event(request_id, "Solicitud creada", reason, requested_by)
                    st.rerun()

    with approval_tab:
        pending = [item for item in requests if item.get("status") == "Pendiente"]
        if not pending:
            st.info("No hay solicitudes pendientes de aprobación.")
        for request in reversed(pending):
            production = next((item for item in _rows("production_log") if str(item.get("production_id", "")) == str(request.get("production_id", ""))), {})
            simulation = _simulate(production, request, products, inventory) if production else []
            with st.container(border=True):
                st.markdown(f"### {request.get('request_id', '')} · {request.get('product_name', '')}")
                st.caption(f"{request.get('reversal_type')} · {request.get('quantity')} unidad(es) · {request.get('priority')} · solicitado por {request.get('requested_by')}")
                cols = st.columns(3)
                cols[0].metric("Material recuperable", format_money(sum(line["unit_cost"] * line["recoverable"] for line in simulation)))
                cols[1].metric("Costo perdido", format_money(sum(line["unit_cost"] * line["lost"] for line in simulation)))
                cols[2].metric("Componentes", str(len(simulation)))
                with st.expander("Ver simulación"):
                    for line in simulation:
                        st.write(f"**{line['name']}** · {line['quantity']:,.2f} · {line['destination']} · costo {format_money(line['cost'])}")
                with st.form(f"approve_reversal_{request.get('request_id')}"):
                    decision = st.selectbox("Decisión", ("Aprobar", "Rechazar"), key=f"decision_{request.get('request_id')}")
                    responsible = st.text_input("Aprobado/Rechazado por", key=f"approver_{request.get('request_id')}")
                    note = st.text_area("Nota de aprobación", max_chars=500, key=f"approval_note_{request.get('request_id')}")
                    submitted = st.form_submit_button("Guardar decisión", type="primary", use_container_width=True)
                if submitted:
                    if not responsible.strip():
                        st.error("Indica quién toma la decisión.")
                    else:
                        status = "Aprobado" if decision == "Aprobar" else "Rechazado"
                        _update_request(str(request.get("request_id", "")), {
                            "status": status,
                            "approved_by": responsible.strip() if status == "Aprobado" else "",
                            "rejected_by": responsible.strip() if status == "Rechazado" else "",
                            "approval_note": note.strip(),
                            "approval_at_utc": _now(),
                        })
                        _add_event(str(request.get("request_id", "")), status, note or decision, responsible)
                        st.rerun()

    with execute_tab:
        approved = [item for item in requests if item.get("status") == "Aprobado"]
        if not approved:
            st.info("No hay reversos aprobados pendientes de ejecución.")
        for request in reversed(approved):
            production = next((item for item in _rows("production_log") if str(item.get("production_id", "")) == str(request.get("production_id", ""))), {})
            simulation = _simulate(production, request, products, inventory) if production else []
            with st.container(border=True):
                st.markdown(f"### {request.get('request_id', '')} · {request.get('product_name', '')}")
                st.write(str(request.get("reason", "")))
                st.metric("Impacto neto estimado", format_money(sum(line["cost"] for line in simulation)))
                with st.form(f"execute_reversal_{request.get('request_id')}"):
                    responsible = st.text_input("Ejecutado por", key=f"execute_owner_{request.get('request_id')}")
                    confirmed = st.checkbox("Confirmo que este reverso aprobado debe ejecutarse", key=f"execute_confirm_{request.get('request_id')}")
                    submitted = st.form_submit_button("Ejecutar reverso", type="primary", use_container_width=True)
                if submitted:
                    if not production:
                        st.error("La producción vinculada no existe.")
                    elif not responsible.strip() or not confirmed:
                        st.error("Indica responsable y confirma la ejecución.")
                    else:
                        request = dict(request)
                        request["approved_by"] = request.get("approved_by") or responsible.strip()
                        _execute_request(request, production, products, inventory, movements, stock)
                        st.rerun()

    with dashboard_tab:
        by_reason = Counter(str(item.get("reason", "Sin motivo"))[:40] for item in requests)
        by_product: dict[str, float] = defaultdict(float)
        for request in requests:
            if request.get("status") == "Ejecutado":
                by_product[str(request.get("product_name", "Producción"))] += _num(request.get("quantity"))
        st.markdown("#### Reversos ejecutados por producto")
        if not by_product:
            st.info("Todavía no hay reversos ejecutados.")
        for product, quantity in sorted(by_product.items(), key=lambda item: item[1], reverse=True)[:10]:
            st.write(f"**{product}:** {quantity:,.2f} unidad(es)")
        st.markdown("#### Motivos frecuentes")
        for reason, count in by_reason.most_common(10):
            st.write(f"**{reason}:** {count}")

    with history_tab:
        request_filter = st.selectbox("Filtrar", ("Todos", *[str(item.get("request_id", "")) for item in requests]), key="reversal_history_filter")
        visible = events if request_filter == "Todos" else [item for item in events if str(item.get("request_id", "")) == request_filter]
        if not visible:
            st.info("No hay eventos registrados.")
        for event in reversed(visible[-100:]):
            with st.container(border=True):
                st.markdown(f"**{event.get('event_type', 'Evento')} · {event.get('request_id', '')}**")
                st.write(str(event.get("note", "")))
                st.caption(f"{event.get('created_at_utc', '')} · {event.get('responsible', 'Sin asignar')}")

    render_info_card(
        "Reverso controlado",
        "Cada reverso requiere solicitud, simulación, aprobación y ejecución para proteger inventario y costos.",
        "PRODUCCIÓN",
    )
