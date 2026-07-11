"""Integridad, edición, planificación y reversos para catálogo y producción."""

from collections import defaultdict
from datetime import date, timedelta
from uuid import uuid4

import streamlit as st

from src import catalog as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("production_plans", "Planes de producción"),
        ("production_events", "Eventos de producción"),
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


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _inventory_map(inventory: list[dict]) -> dict[str, dict]:
    return {str(item.get("item_id", "")): dict(item) for item in inventory}


def _consolidate_recipe(recipe: list[dict]) -> list[dict]:
    quantities: dict[str, float] = defaultdict(float)
    for component in recipe:
        item_id = str(component.get("item_id", "")).strip()
        quantity = _num(component.get("quantity"))
        if item_id and quantity > 0:
            quantities[item_id] += quantity
    return [{"item_id": item_id, "quantity": quantity} for item_id, quantity in quantities.items()]


def _recipe_cost(recipe: list[dict], inventory: list[dict]) -> float:
    items = _inventory_map(inventory)
    total = 0.0
    for component in _consolidate_recipe(recipe):
        item = items.get(str(component.get("item_id", "")))
        if not item:
            continue
        purchased = max(_num(item.get("purchased_quantity"), 1.0), 0.01)
        unit_cost = _num(item.get("purchase_cost")) / purchased
        total += unit_cost * _num(component.get("quantity"))
    return total


def _update_product(product_id: str, updates: dict) -> None:
    products = _rows("products_registry")
    changed = []
    for product in products:
        row = dict(product)
        if str(row.get("product_id", "")) == product_id:
            row.update(updates)
            row["updated_at_utc"] = _now()
        changed.append(row)
    _save("products_registry", changed)


def _add_event(production_id: str, event_type: str, note: str, responsible: str = "") -> None:
    events = _rows("production_events")
    events.append({
        "event_id": uuid4().hex[:12],
        "production_id": production_id,
        "event_type": event_type,
        "note": note.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("production_events", events)


def _reversal_recipe(production: dict, products: list[dict]) -> list[dict]:
    snapshot = [dict(item) for item in production.get("recipe_snapshot", []) if isinstance(item, dict)]
    if snapshot:
        return _consolidate_recipe(snapshot)
    product_id = str(production.get("product_id", ""))
    product = next((item for item in products if str(item.get("product_id", "")) == product_id), {})
    return _consolidate_recipe([dict(item) for item in product.get("recipe", []) if isinstance(item, dict)])


def _reverse_production(production: dict, products: list[dict], inventory: list[dict], movements: list[dict]) -> tuple[list[dict], list[dict]]:
    recipe = _reversal_recipe(production, products)
    quantity = _num(production.get("quantity"))
    returned = {str(item.get("item_id", "")): _num(item.get("quantity")) * quantity for item in recipe}
    updated_inventory = []
    for item in inventory:
        row = dict(item)
        item_id = str(row.get("item_id", ""))
        if item_id in returned:
            previous = _num(row.get("available_quantity"))
            resulting = previous + returned[item_id]
            row["available_quantity"] = resulting
            movements.append({
                "movement_id": uuid4().hex[:10],
                "created_at_utc": _now(),
                "item_id": item_id,
                "item_name": str(row.get("name", "Material")),
                "movement_type": "Entrada",
                "quantity": returned[item_id],
                "unit_name": str(row.get("unit_name", "unidad")),
                "reason": f"Reverso de producción {production.get('production_id', '')}",
                "previous_quantity": previous,
                "resulting_quantity": resulting,
            })
        updated_inventory.append(row)
    return updated_inventory, movements


def render_catalog_production_plus() -> None:
    render_page_header(
        "Catálogo y producción",
        "Administra productos, recetas y producción con integridad, planificación y reversos seguros.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_catalog()
    finally:
        base.render_page_header = original_header

    products = _rows("products_registry")
    inventory = _rows("inventory_registry")
    movements = _rows("inventory_movements")
    production_log = _rows("production_log")
    plans = _rows("production_plans")

    duplicates = []
    incomplete = []
    unprofitable = []
    for product in products:
        recipe = [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
        ids = [str(item.get("item_id", "")) for item in recipe if item.get("item_id")]
        if len(ids) != len(set(ids)):
            duplicates.append(product)
        if product.get("product_type") == "Producto" and not recipe:
            incomplete.append(product)
        cost = _recipe_cost(recipe, inventory) + _num(product.get("extra_cost"))
        if _num(product.get("sale_price")) <= cost:
            unprofitable.append(product)

    st.divider()
    st.markdown("### Control de catálogo y producción")
    metrics = st.columns(4)
    metrics[0].metric("Duplicados en recetas", str(len(duplicates)))
    metrics[1].metric("Productos incompletos", str(len(incomplete)))
    metrics[2].metric("Precio sin margen", str(len(unprofitable)))
    metrics[3].metric("Planes abiertos", str(sum(1 for item in plans if item.get("status", "Pendiente") != "Completado")))

    if duplicates:
        st.error(f"Hay {len(duplicates)} producto(s) con materiales repetidos en la receta.")
    if unprofitable:
        st.warning(f"Hay {len(unprofitable)} producto(s) cuyo precio no supera el costo calculado.")

    edit_tab, integrity_tab, planning_tab, reversal_tab, history_tab = st.tabs(
        ("Editar catálogo", "Integridad de recetas", "Planificación", "Reversos", "Historial")
    )

    product_options = {
        f"{item.get('name', 'Producto')} · {item.get('product_id', '')}": str(item.get("product_id", ""))
        for item in products
    }

    with edit_tab:
        if not product_options:
            st.info("No hay productos o servicios registrados.")
        else:
            selected = st.selectbox("Producto o servicio", tuple(product_options.keys()), key="catalog_edit_selected")
            product_id = product_options[selected]
            product = next(item for item in products if str(item.get("product_id", "")) == product_id)
            with st.form("catalog_edit_form"):
                first = st.columns(3)
                name = first[0].text_input("Nombre", value=str(product.get("name", "")))
                sku = first[1].text_input("SKU", value=str(product.get("sku", "")))
                active = first[2].checkbox("Activo", value=bool(product.get("active", True)))
                second = st.columns(3)
                sale_price = second[0].number_input("Precio de venta", min_value=0.0, value=_num(product.get("sale_price")), step=0.5)
                extra_cost = second[1].number_input("Otros costos", min_value=0.0, value=_num(product.get("extra_cost")), step=0.1)
                category = second[2].text_input("Categoría", value=str(product.get("category", "")))
                notes = st.text_area("Notas", value=str(product.get("notes", "")), max_chars=500)
                submitted = st.form_submit_button("Guardar cambios", type="primary", use_container_width=True)
            if submitted:
                if not name.strip():
                    st.error("El nombre no puede quedar vacío.")
                elif sale_price <= 0:
                    st.error("El precio de venta debe ser mayor que cero.")
                else:
                    _update_product(product_id, {
                        "name": name.strip(),
                        "sku": sku.strip(),
                        "active": active,
                        "sale_price": float(sale_price),
                        "extra_cost": float(extra_cost),
                        "category": category.strip() or "Otro",
                        "notes": notes.strip(),
                    })
                    st.rerun()

    with integrity_tab:
        if not products:
            st.info("No hay recetas para revisar.")
        for product in products:
            recipe = [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
            consolidated = _consolidate_recipe(recipe)
            if len(recipe) == len(consolidated):
                continue
            with st.container(border=True):
                st.markdown(f"**{product.get('name', 'Producto')}**")
                st.write(f"Componentes actuales: {len(recipe)} · componentes consolidados: {len(consolidated)}")
                if st.button("Consolidar receta", key=f"consolidate_recipe_{product.get('product_id')}", use_container_width=True):
                    _update_product(str(product.get("product_id", "")), {"recipe": consolidated})
                    st.rerun()
        if products and not duplicates:
            st.success("No se detectaron materiales repetidos en las recetas.")

    with planning_tab:
        if not product_options:
            st.info("No hay productos para planificar.")
        else:
            selected = st.selectbox("Producto", tuple(product_options.keys()), key="production_plan_product")
            product_id = product_options[selected]
            product = next(item for item in products if str(item.get("product_id", "")) == product_id)
            with st.form("production_plan_form", clear_on_submit=True):
                columns = st.columns(4)
                quantity = columns[0].number_input("Cantidad planificada", min_value=1.0, value=1.0, step=1.0)
                due_date = columns[1].date_input("Fecha objetivo", value=date.today() + timedelta(days=1))
                priority = columns[2].selectbox("Prioridad", ("Baja", "Normal", "Alta", "Urgente"))
                responsible = columns[3].text_input("Responsable")
                note = st.text_area("Observaciones", max_chars=500)
                submitted = st.form_submit_button("Crear plan", type="primary", use_container_width=True)
            if submitted:
                plans.append({
                    "plan_id": f"PROD-{uuid4().hex[:8].upper()}",
                    "product_id": product_id,
                    "product_name": str(product.get("name", "Producto")),
                    "quantity": float(quantity),
                    "due_date": due_date.isoformat(),
                    "priority": priority,
                    "responsible": responsible.strip() or "Sin asignar",
                    "note": note.strip(),
                    "status": "Pendiente",
                    "created_at_utc": _now(),
                })
                _save("production_plans", plans)
                st.rerun()

            for plan in reversed(plans[-50:]):
                with st.container(border=True):
                    columns = st.columns([3, 1, 1, 1])
                    columns[0].markdown(f"**{plan.get('product_name', 'Producción')}**")
                    columns[0].caption(f"{plan.get('plan_id', '')} · Responsable: {plan.get('responsible', '')}")
                    columns[1].metric("Cantidad", f"{_num(plan.get('quantity')):,.2f}")
                    columns[2].metric("Fecha", str(plan.get("due_date", "")))
                    columns[3].metric("Estado", str(plan.get("status", "Pendiente")))
                    if plan.get("status") != "Completado" and st.button("Marcar completado", key=f"complete_plan_{plan.get('plan_id')}", use_container_width=True):
                        updated = []
                        for current in plans:
                            row = dict(current)
                            if row.get("plan_id") == plan.get("plan_id"):
                                row["status"] = "Completado"
                                row["completed_at_utc"] = _now()
                            updated.append(row)
                        _save("production_plans", updated)
                        st.rerun()

    with reversal_tab:
        reversible = [item for item in production_log if not item.get("reversed")]
        if not reversible:
            st.info("No hay producciones disponibles para reversar.")
        else:
            labels = {
                f"{item.get('product_name', 'Producción')} · {item.get('production_id', '')} · {item.get('quantity', 0)}": str(item.get("production_id", ""))
                for item in reversible
            }
            selected = st.selectbox("Producción", tuple(labels.keys()), key="production_reverse_selected")
            production_id = labels[selected]
            production = next(item for item in reversible if str(item.get("production_id", "")) == production_id)
            with st.form("production_reversal_form"):
                responsible = st.text_input("Responsable")
                reason = st.text_area("Motivo del reverso", max_chars=500)
                confirmed = st.checkbox("Confirmo que deseo devolver los materiales al inventario")
                submitted = st.form_submit_button("Reversar producción", type="primary", use_container_width=True)
            if submitted:
                if not confirmed or not reason.strip():
                    st.error("Confirma la acción e indica el motivo.")
                else:
                    updated_inventory, updated_movements = _reverse_production(production, products, inventory, movements)
                    updated_log = []
                    for item in production_log:
                        row = dict(item)
                        if str(row.get("production_id", "")) == production_id:
                            row["reversed"] = True
                            row["reversed_at_utc"] = _now()
                            row["reversal_reason"] = reason.strip()
                            row["reversed_by"] = responsible.strip() or "Sin asignar"
                        updated_log.append(row)
                    _save("inventory_registry", updated_inventory)
                    _save("inventory_movements", updated_movements)
                    _save("production_log", updated_log)
                    _add_event(production_id, "Producción reversada", reason, responsible)
                    st.rerun()

    with history_tab:
        if not production_log:
            st.info("No hay producciones registradas.")
        for production in reversed(production_log[-100:]):
            with st.container(border=True):
                columns = st.columns(4)
                columns[0].metric("Producto", str(production.get("product_name", "")))
                columns[1].metric("Cantidad", f"{_num(production.get('quantity')):,.2f}")
                columns[2].metric("Costo total", format_money(_num(production.get("total_cost"))))
                columns[3].metric("Estado", "Reversada" if production.get("reversed") else "Vigente")
                st.caption(f"{production.get('production_id', '')} · {production.get('created_at_utc', '')}")
                snapshot = _reversal_recipe(production, products)
                if snapshot:
                    st.caption(f"Receta utilizada: {len(snapshot)} componente(s).")

    render_info_card(
        "Producción trazable",
        "Ediciones, planes y reversos conservan historial y se incluyen en el respaldo general.",
        "CATÁLOGO Y PRODUCCIÓN",
    )
