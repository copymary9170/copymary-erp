"""Mantenimiento, calidad de datos y trazabilidad del catálogo."""

from collections import defaultdict
from datetime import date, datetime
from uuid import uuid4
import csv
import io

import streamlit as st

from src import session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("catalog_change_log", "Historial de mantenimiento del catálogo"),
        ("catalog_recipe_versions", "Versiones de recetas"),
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


def _aggregate(recipe: list[dict]) -> list[dict]:
    totals: dict[str, float] = defaultdict(float)
    for component in recipe:
        item_id = str(component.get("item_id", "")).strip()
        quantity = _num(component.get("quantity"))
        if item_id and quantity > 0:
            totals[item_id] += quantity
    return [{"item_id": item_id, "quantity": quantity} for item_id, quantity in totals.items()]


def _recipe_cost(recipe: list[dict], inventory: list[dict]) -> float:
    items = {str(item.get("item_id", "")): item for item in inventory}
    total = 0.0
    for component in _aggregate(recipe):
        item = items.get(str(component.get("item_id", "")))
        if not item:
            continue
        purchased = max(_num(item.get("purchased_quantity"), 1.0), 0.01)
        total += (_num(item.get("purchase_cost")) / purchased) * _num(component.get("quantity"))
    return total


def _log(product_id: str, action: str, details: str, responsible: str = "") -> None:
    records = _rows("catalog_change_log")
    records.append({
        "change_id": uuid4().hex[:12],
        "product_id": product_id,
        "action": action,
        "details": details.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("catalog_change_log", records)


def _snapshot(product: dict, reason: str, responsible: str = "") -> None:
    versions = _rows("catalog_recipe_versions")
    product_id = str(product.get("product_id", ""))
    count = sum(1 for item in versions if str(item.get("product_id", "")) == product_id)
    versions.append({
        "version_id": uuid4().hex[:12],
        "product_id": product_id,
        "version_number": count + 1,
        "recipe": [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)],
        "sale_price": _num(product.get("sale_price")),
        "extra_cost": _num(product.get("extra_cost")),
        "reason": reason.strip() or "Actualización de catálogo",
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("catalog_recipe_versions", versions)


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


def _duplicate_groups(products: list[dict], field: str) -> list[list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for product in products:
        key = str(product.get(field, "")).strip().casefold()
        if key:
            grouped[key].append(product)
    return [items for items in grouped.values() if len(items) > 1]


def _export(products: list[dict], inventory: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "SKU", "Nombre", "Tipo", "Categoría", "Activo", "Precio", "Costo", "Margen", "Última revisión", "Componentes", "Estado de datos"])
    inventory_ids = {str(item.get("item_id", "")) for item in inventory}
    for product in products:
        recipe = [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
        cost = _recipe_cost(recipe, inventory) + _num(product.get("extra_cost"))
        price = _num(product.get("sale_price"))
        margin = (price - cost) / price * 100 if price > 0 else 0.0
        issues = []
        if not product.get("sku"):
            issues.append("Sin SKU")
        if product.get("product_type") == "Producto" and not recipe:
            issues.append("Sin receta")
        if price <= cost:
            issues.append("Sin margen")
        if any(str(item.get("item_id", "")) not in inventory_ids for item in recipe):
            issues.append("Receta rota")
        writer.writerow([product.get("product_id", ""), product.get("sku", ""), product.get("name", ""), product.get("product_type", ""), product.get("category", ""), "Sí" if product.get("active", True) else "No", price, cost, margin, product.get("last_reviewed_at_utc", ""), len(recipe), ", ".join(issues) or "Correcto"])
    return buffer.getvalue().encode("utf-8-sig")


def render_catalog_maintenance() -> None:
    render_page_header("Mantenimiento del catálogo", "Depura, revisa, versiona y conserva actualizado el catálogo sin perder historial.")

    products = _rows("products_registry")
    inventory = _rows("inventory_registry")
    changes = _rows("catalog_change_log")
    versions = _rows("catalog_recipe_versions")
    today = datetime.now()
    inventory_ids = {str(item.get("item_id", "")) for item in inventory}

    duplicate_skus = _duplicate_groups(products, "sku")
    duplicate_names = _duplicate_groups(products, "name")
    stale, missing_sku, no_margin, broken_recipe = [], [], [], []
    for product in products:
        reviewed = _as_datetime(product.get("last_reviewed_at_utc", product.get("updated_at_utc", product.get("created_at_utc"))))
        if not reviewed or (today - reviewed).days > 90:
            stale.append(product)
        if not str(product.get("sku", "")).strip():
            missing_sku.append(product)
        recipe = [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
        cost = _recipe_cost(recipe, inventory) + _num(product.get("extra_cost"))
        if _num(product.get("sale_price")) <= cost:
            no_margin.append(product)
        if any(str(item.get("item_id", "")) not in inventory_ids for item in recipe):
            broken_recipe.append(product)

    metrics = st.columns(6)
    metrics[0].metric("Productos", str(len(products)))
    metrics[1].metric("Sin SKU", str(len(missing_sku)))
    metrics[2].metric("SKU duplicados", str(len(duplicate_skus)))
    metrics[3].metric("Nombres duplicados", str(len(duplicate_names)))
    metrics[4].metric("Sin revisar 90 días", str(len(stale)))
    metrics[5].metric("Recetas rotas", str(len(broken_recipe)))

    if no_margin:
        st.warning(f"Hay {len(no_margin)} registro(s) cuyo precio no supera el costo calculado.")
    if broken_recipe:
        st.error(f"Hay {len(broken_recipe)} producto(s) con materiales inexistentes en la receta.")

    search_tab, review_tab, duplicate_tab, clone_tab, version_tab, history_tab = st.tabs(("Buscar y editar", "Revisión periódica", "Duplicados", "Clonar", "Versiones", "Historial"))

    with search_tab:
        filters = st.columns(4)
        query = filters[0].text_input("Buscar", placeholder="Nombre, SKU, categoría o ID").strip().casefold()
        status_filter = filters[1].selectbox("Estado", ("Todos", "Activos", "Archivados"))
        type_filter = filters[2].selectbox("Tipo", ("Todos", "Producto", "Servicio"))
        issue_filter = filters[3].selectbox("Problema", ("Todos", "Sin SKU", "Sin margen", "Receta rota", "Sin revisar"))

        filtered = []
        for product in products:
            text = " ".join(str(product.get(field, "")) for field in ("name", "sku", "category", "product_id")).casefold()
            if query and query not in text:
                continue
            active = bool(product.get("active", True))
            if status_filter == "Activos" and not active:
                continue
            if status_filter == "Archivados" and active:
                continue
            if type_filter != "Todos" and str(product.get("product_type", "")) != type_filter:
                continue
            if issue_filter == "Sin SKU" and product not in missing_sku:
                continue
            if issue_filter == "Sin margen" and product not in no_margin:
                continue
            if issue_filter == "Receta rota" and product not in broken_recipe:
                continue
            if issue_filter == "Sin revisar" and product not in stale:
                continue
            filtered.append(product)

        st.caption(f"Mostrando {len(filtered)} de {len(products)} registro(s).")
        for product in filtered:
            product_id = str(product.get("product_id", ""))
            recipe = [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
            cost = _recipe_cost(recipe, inventory) + _num(product.get("extra_cost"))
            price = _num(product.get("sale_price"))
            margin = (price - cost) / price * 100 if price > 0 else 0.0
            with st.container(border=True):
                header = st.columns([3, 1, 1])
                header[0].markdown(f"### {product.get('name', 'Producto')}")
                header[0].caption(f"{product_id} · SKU {product.get('sku') or 'Sin SKU'} · {product.get('category', '')}")
                header[1].metric("Precio", format_money(price))
                header[2].metric("Margen", f"{margin:,.1f}%")
                with st.expander("Editar mantenimiento"):
                    with st.form(f"catalog_maintenance_{product_id}"):
                        first = st.columns(4)
                        name = first[0].text_input("Nombre", value=str(product.get("name", "")), key=f"maint_name_{product_id}")
                        sku = first[1].text_input("SKU", value=str(product.get("sku", "")), key=f"maint_sku_{product_id}")
                        price_value = first[2].number_input("Precio", min_value=0.0, value=price, step=0.5, key=f"maint_price_{product_id}")
                        active = first[3].checkbox("Activo", value=bool(product.get("active", True)), key=f"maint_active_{product_id}")
                        second = st.columns(3)
                        category = second[0].text_input("Categoría", value=str(product.get("category", "")), key=f"maint_category_{product_id}")
                        extra_cost = second[1].number_input("Otros costos", min_value=0.0, value=_num(product.get("extra_cost")), step=0.1, key=f"maint_extra_{product_id}")
                        responsible = second[2].text_input("Responsable", key=f"maint_resp_{product_id}")
                        reason = st.text_area("Motivo del cambio", max_chars=500, key=f"maint_reason_{product_id}")
                        submitted = st.form_submit_button("Guardar mantenimiento", type="primary", use_container_width=True)
                    if submitted:
                        same_sku = any(str(item.get("product_id", "")) != product_id and sku.strip() and str(item.get("sku", "")).strip().casefold() == sku.strip().casefold() for item in products)
                        if not name.strip():
                            st.error("El nombre no puede quedar vacío.")
                        elif price_value <= 0:
                            st.error("El precio debe ser mayor que cero.")
                        elif same_sku:
                            st.error("Ese SKU ya está siendo utilizado por otro registro.")
                        else:
                            _snapshot(product, reason, responsible)
                            _update_product(product_id, {"name": name.strip(), "sku": sku.strip(), "sale_price": float(price_value), "active": active, "category": category.strip() or "Otro", "extra_cost": float(extra_cost), "recipe": _aggregate(recipe), "last_reviewed_at_utc": _now()})
                            _log(product_id, "Mantenimiento", reason or "Actualización de ficha", responsible)
                            st.rerun()

    with review_tab:
        if not stale:
            st.success("Todo el catálogo fue revisado durante los últimos 90 días.")
        for product in stale:
            product_id = str(product.get("product_id", ""))
            reviewed = _as_datetime(product.get("last_reviewed_at_utc", product.get("updated_at_utc", product.get("created_at_utc"))))
            days = (today - reviewed).days if reviewed else None
            with st.container(border=True):
                columns = st.columns([3, 1, 1])
                columns[0].markdown(f"**{product.get('name', 'Producto')}**")
                columns[0].caption(f"Última revisión: {reviewed.date().isoformat() if reviewed else 'Nunca'}")
                columns[1].metric("Días", str(days) if days is not None else "Sin dato")
                if columns[2].button("Marcar revisado", key=f"review_catalog_{product_id}", use_container_width=True):
                    _update_product(product_id, {"last_reviewed_at_utc": _now()})
                    _log(product_id, "Revisión periódica", "Ficha revisada sin cambios")
                    st.rerun()

    with duplicate_tab:
        if not duplicate_skus and not duplicate_names:
            st.success("No se detectaron SKU ni nombres duplicados.")
        for title, groups in (("SKU duplicados", duplicate_skus), ("Nombres duplicados", duplicate_names)):
            if groups:
                st.markdown(f"#### {title}")
            for group in groups:
                with st.container(border=True):
                    st.write(" · ".join(f"{item.get('name', '')} ({item.get('product_id', '')})" for item in group))
                    st.caption("Mantén identificadores únicos para evitar errores en ventas, inventario y reportes.")

    with clone_tab:
        active_products = [item for item in products if item.get("active", True)]
        if not active_products:
            st.info("No hay productos activos para clonar.")
        else:
            options = {f"{item.get('name', 'Producto')} · {item.get('sku') or 'Sin SKU'}": str(item.get("product_id", "")) for item in active_products}
            with st.form("catalog_clone_form"):
                selected = st.selectbox("Registro base", tuple(options.keys()))
                columns = st.columns(3)
                new_name = columns[0].text_input("Nuevo nombre")
                new_sku = columns[1].text_input("Nuevo SKU")
                price_adjustment = columns[2].number_input("Ajuste de precio", value=0.0, step=0.5)
                responsible = st.text_input("Responsable")
                submitted = st.form_submit_button("Clonar registro", type="primary", use_container_width=True)
            if submitted:
                source = next(item for item in products if str(item.get("product_id", "")) == options[selected])
                duplicate = any(str(item.get("sku", "")).strip().casefold() == new_sku.strip().casefold() for item in products if new_sku.strip())
                if not new_name.strip() or not new_sku.strip():
                    st.error("Indica nombre y SKU para el nuevo registro.")
                elif duplicate:
                    st.error("El nuevo SKU ya existe.")
                else:
                    clone = dict(source)
                    clone.update({"product_id": uuid4().hex[:10], "name": new_name.strip(), "sku": new_sku.strip(), "sale_price": max(_num(source.get("sale_price")) + float(price_adjustment), 0.01), "created_at_utc": _now(), "updated_at_utc": _now(), "last_reviewed_at_utc": _now(), "active": True})
                    products.append(clone)
                    _save("products_registry", products)
                    _log(str(clone.get("product_id", "")), "Clonado", f"Creado desde {source.get('product_id', '')}", responsible)
                    st.rerun()

    with version_tab:
        options = {f"{item.get('name', 'Producto')} · {item.get('product_id', '')}": str(item.get("product_id", "")) for item in products}
        if not options:
            st.info("No hay productos para consultar versiones.")
        else:
            selected = st.selectbox("Producto", tuple(options.keys()), key="catalog_version_product")
            visible = [item for item in versions if str(item.get("product_id", "")) == options[selected]]
            if not visible:
                st.info("Este producto aún no tiene versiones guardadas.")
            for version in reversed(visible):
                with st.container(border=True):
                    columns = st.columns(4)
                    columns[0].metric("Versión", str(version.get("version_number", "")))
                    columns[1].metric("Precio", format_money(_num(version.get("sale_price"))))
                    columns[2].metric("Costo adicional", format_money(_num(version.get("extra_cost"))))
                    columns[3].metric("Componentes", str(len(version.get("recipe", []))))
                    st.caption(f"{version.get('created_at_utc', '')} · {version.get('responsible', 'Sin asignar')} · {version.get('reason', '')}")

    with history_tab:
        query = st.text_input("Buscar en historial", placeholder="Producto, acción, responsable o detalle").strip().casefold()
        product_names = {str(item.get("product_id", "")): str(item.get("name", "Producto")) for item in products}
        visible = []
        for change in changes:
            text = " ".join((str(change.get("product_id", "")), product_names.get(str(change.get("product_id", "")), ""), str(change.get("action", "")), str(change.get("details", "")), str(change.get("responsible", "")))).casefold()
            if not query or query in text:
                visible.append(change)
        if not visible:
            st.info("No hay cambios que coincidan con la búsqueda.")
        for change in reversed(visible[-100:]):
            with st.container(border=True):
                st.markdown(f"**{change.get('action', 'Cambio')} · {product_names.get(str(change.get('product_id', '')), change.get('product_id', ''))}**")
                st.write(str(change.get("details", "")))
                st.caption(f"{change.get('created_at_utc', '')} · {change.get('responsible', 'Sin asignar')}")

    if products:
        st.download_button("Descargar auditoría del catálogo CSV", data=_export(products, inventory), file_name=f"mantenimiento_catalogo_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True)

    render_info_card("Catálogo confiable", "Las revisiones, versiones, clonaciones y cambios quedan registrados y forman parte del respaldo general.", "MANTENIMIENTO")
