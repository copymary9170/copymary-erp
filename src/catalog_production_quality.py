"""Lotes, calidad, variantes y producto terminado para CopyMary ERP."""

from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src import catalog_production_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money


def _activate_backup() -> None:
    for section, label in (
        ("production_batches", "Lotes de producción"),
        ("finished_goods_stock", "Inventario de producto terminado"),
        ("product_variants", "Variantes de productos"),
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


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, rows: list[dict]) -> None:
    st.session_state[key] = rows


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _product_name(product_id: str, products: list[dict]) -> str:
    for product in products:
        if str(product.get("product_id", "")) == product_id:
            return str(product.get("name", "Producto"))
    return "Producto no disponible"


def _variant_name(variant_id: str, variants: list[dict]) -> str:
    if not variant_id:
        return "Sin variante"
    for variant in variants:
        if str(variant.get("variant_id", "")) == variant_id:
            return str(variant.get("name", "Variante"))
    return "Variante no disponible"


def _update_production(production_id: str, updates: dict) -> None:
    productions = _rows("production_log")
    changed = []
    for production in productions:
        row = dict(production)
        if str(row.get("production_id", "")) == production_id:
            row.update(updates)
            row["updated_at_utc"] = _now()
        changed.append(row)
    _save("production_log", changed)


def _add_finished_stock(product_id: str, variant_id: str, quantity: float, batch_id: str) -> None:
    stock = _rows("finished_goods_stock")
    found = False
    for item in stock:
        if str(item.get("product_id", "")) == product_id and str(item.get("variant_id", "")) == variant_id:
            item["quantity"] = _num(item.get("quantity")) + quantity
            item["last_batch_id"] = batch_id
            item["updated_at_utc"] = _now()
            found = True
            break
    if not found:
        stock.append({
            "stock_id": uuid4().hex[:12],
            "product_id": product_id,
            "variant_id": variant_id,
            "quantity": quantity,
            "last_batch_id": batch_id,
            "updated_at_utc": _now(),
        })
    _save("finished_goods_stock", stock)


def _batch_code() -> str:
    return f"LOT-{date.today().strftime('%Y%m%d')}-{uuid4().hex[:5].upper()}"


def render_catalog_production_quality() -> None:
    render_page_header(
        "Catálogo y producción",
        "Controla variantes, lotes, calidad, merma y existencias de producto terminado.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_catalog_production_plus()
    finally:
        base.render_page_header = original_header

    products = _rows("products_registry")
    productions = _rows("production_log")
    batches = _rows("production_batches")
    stock = _rows("finished_goods_stock")
    variants = _rows("product_variants")

    approved_units = sum(_num(item.get("accepted_quantity")) for item in batches)
    rejected_units = sum(_num(item.get("rejected_quantity")) for item in batches)
    total_inspected = approved_units + rejected_units
    rejection_rate = rejected_units / total_inspected * 100 if total_inspected else 0.0
    finished_units = sum(_num(item.get("quantity")) for item in stock)
    pending_qc = [
        item for item in productions
        if not item.get("reversed") and not item.get("batch_id")
    ]

    st.divider()
    st.markdown("### Calidad y producto terminado")
    metrics = st.columns(5)
    metrics[0].metric("Producciones sin revisar", str(len(pending_qc)))
    metrics[1].metric("Unidades aprobadas", f"{approved_units:,.2f}")
    metrics[2].metric("Unidades rechazadas", f"{rejected_units:,.2f}")
    metrics[3].metric("Tasa de rechazo", f"{rejection_rate:,.1f}%")
    metrics[4].metric("Producto terminado", f"{finished_units:,.2f}")

    if rejection_rate > 10:
        st.warning("La tasa de rechazo supera el 10%; conviene revisar materiales, proceso y operador.")

    quality_tab, stock_tab, variants_tab, trace_tab = st.tabs(
        ("Control de calidad", "Producto terminado", "Variantes", "Trazabilidad")
    )

    with quality_tab:
        if not pending_qc:
            st.success("Todas las producciones vigentes tienen control de calidad registrado.")
        else:
            options = {
                f"{item.get('product_name', 'Producción')} · {item.get('production_id', '')} · {item.get('quantity', 0)} unidades": str(item.get("production_id", ""))
                for item in pending_qc
            }
            selected = st.selectbox("Producción por inspeccionar", tuple(options.keys()))
            production_id = options[selected]
            production = next(item for item in pending_qc if str(item.get("production_id", "")) == production_id)
            produced = _num(production.get("quantity"))
            product_id = str(production.get("product_id", ""))
            product_variants = [item for item in variants if str(item.get("product_id", "")) == product_id and item.get("active", True)]
            variant_options = {"Sin variante": ""}
            for variant in product_variants:
                variant_options[f"{variant.get('name', 'Variante')} · {variant.get('variant_id', '')}"] = str(variant.get("variant_id", ""))

            with st.form("production_quality_form"):
                first = st.columns(4)
                selected_variant = first[0].selectbox("Variante", tuple(variant_options.keys()))
                status = first[1].selectbox("Resultado", ("Aprobado", "Aprobado con observación", "Rechazado"))
                accepted = first[2].number_input("Unidades aprobadas", min_value=0.0, max_value=float(produced), value=float(produced), step=1.0)
                rejected = first[3].number_input("Unidades rechazadas", min_value=0.0, max_value=float(produced), value=0.0, step=1.0)
                second = st.columns(3)
                inspector = second[0].text_input("Inspector o responsable")
                batch_reference = second[1].text_input("Referencia del lote", value=_batch_code())
                expiry = second[2].date_input("Fecha de vencimiento", value=None)
                defects = st.multiselect(
                    "Defectos observados",
                    ("Color", "Corte", "Impresión", "Medida", "Adhesión", "Mancha", "Empaque", "Otro"),
                )
                notes = st.text_area("Observaciones de calidad", max_chars=700)
                submitted = st.form_submit_button("Cerrar inspección y crear lote", type="primary", use_container_width=True)

            if submitted:
                if abs((accepted + rejected) - produced) > 0.0001:
                    st.error("Las unidades aprobadas y rechazadas deben sumar exactamente la cantidad producida.")
                elif status == "Rechazado" and accepted > 0:
                    st.error("Una producción rechazada no puede registrar unidades aprobadas.")
                elif not batch_reference.strip():
                    st.error("La referencia del lote es obligatoria.")
                elif any(str(item.get("batch_code", "")).casefold() == batch_reference.strip().casefold() for item in batches):
                    st.error("Ya existe un lote con esa referencia.")
                else:
                    batch_id = uuid4().hex[:12]
                    unit_cost = _num(production.get("unit_cost"))
                    batches.append({
                        "batch_id": batch_id,
                        "batch_code": batch_reference.strip(),
                        "production_id": production_id,
                        "product_id": product_id,
                        "variant_id": variant_options[selected_variant],
                        "produced_quantity": produced,
                        "accepted_quantity": float(accepted),
                        "rejected_quantity": float(rejected),
                        "rejected_cost": float(rejected) * unit_cost,
                        "quality_status": status,
                        "defects": list(defects),
                        "inspector": inspector.strip() or "Sin asignar",
                        "expiry_date": expiry.isoformat() if expiry else "",
                        "notes": notes.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("production_batches", batches)
                    _update_production(production_id, {
                        "batch_id": batch_id,
                        "batch_code": batch_reference.strip(),
                        "quality_status": status,
                        "accepted_quantity": float(accepted),
                        "rejected_quantity": float(rejected),
                    })
                    if accepted > 0:
                        _add_finished_stock(product_id, variant_options[selected_variant], float(accepted), batch_id)
                    st.rerun()

    with stock_tab:
        if not stock:
            st.info("Todavía no hay producto terminado aprobado.")
        product_totals: dict[str, float] = defaultdict(float)
        for item in stock:
            product_totals[_product_name(str(item.get("product_id", "")), products)] += _num(item.get("quantity"))
        for item in sorted(stock, key=lambda row: _num(row.get("quantity")), reverse=True):
            with st.container(border=True):
                columns = st.columns([3, 1, 1])
                columns[0].markdown(f"**{_product_name(str(item.get('product_id', '')), products)}**")
                columns[0].caption(f"{_variant_name(str(item.get('variant_id', '')), variants)} · Último lote {item.get('last_batch_id', '')}")
                columns[1].metric("Existencia", f"{_num(item.get('quantity')):,.2f}")
                columns[2].metric("Actualizado", str(item.get("updated_at_utc", ""))[:10])

    with variants_tab:
        product_options = {
            f"{item.get('name', 'Producto')} · {item.get('product_id', '')}": str(item.get("product_id", ""))
            for item in products if item.get("product_type") == "Producto"
        }
        if not product_options:
            st.info("No hay productos disponibles para crear variantes.")
        else:
            with st.form("product_variant_form", clear_on_submit=True):
                selected_product = st.selectbox("Producto", tuple(product_options.keys()))
                columns = st.columns(3)
                name = columns[0].text_input("Nombre de la variante", placeholder="Ej. Tamaño carta")
                sku_suffix = columns[1].text_input("Sufijo SKU", placeholder="Ej. CARTA")
                price_adjustment = columns[2].number_input("Ajuste de precio", value=0.0, step=0.5)
                notes = st.text_input("Descripción o especificación")
                submitted = st.form_submit_button("Crear variante", type="primary", use_container_width=True)
            if submitted:
                product_id = product_options[selected_product]
                duplicate = any(
                    str(item.get("product_id", "")) == product_id
                    and str(item.get("name", "")).strip().casefold() == name.strip().casefold()
                    for item in variants
                )
                if not name.strip():
                    st.error("El nombre de la variante es obligatorio.")
                elif duplicate:
                    st.error("Ya existe una variante con ese nombre para el producto.")
                else:
                    variants.append({
                        "variant_id": f"VAR-{uuid4().hex[:8].upper()}",
                        "product_id": product_id,
                        "name": name.strip(),
                        "sku_suffix": sku_suffix.strip(),
                        "price_adjustment": float(price_adjustment),
                        "notes": notes.strip(),
                        "active": True,
                        "created_at_utc": _now(),
                    })
                    _save("product_variants", variants)
                    st.rerun()

            for variant in variants:
                product = next((item for item in products if str(item.get("product_id", "")) == str(variant.get("product_id", ""))), {})
                final_price = _num(product.get("sale_price")) + _num(variant.get("price_adjustment"))
                with st.container(border=True):
                    columns = st.columns([3, 1, 1])
                    columns[0].markdown(f"**{variant.get('name', 'Variante')} · {product.get('name', 'Producto')}**")
                    columns[0].caption(f"SKU: {product.get('sku', '')}-{variant.get('sku_suffix', '')}".strip("-"))
                    columns[1].metric("Ajuste", format_money(_num(variant.get("price_adjustment"))))
                    columns[2].metric("Precio final", format_money(final_price))

    with trace_tab:
        query = st.text_input("Buscar lote", placeholder="Código de lote, producto o producción").strip().casefold()
        visible = []
        for batch in batches:
            text = " ".join((
                str(batch.get("batch_code", "")),
                str(batch.get("production_id", "")),
                _product_name(str(batch.get("product_id", "")), products),
                _variant_name(str(batch.get("variant_id", "")), variants),
            )).casefold()
            if not query or query in text:
                visible.append(batch)
        if not visible:
            st.info("No hay lotes que coincidan con la búsqueda.")
        for batch in reversed(visible[-100:]):
            with st.container(border=True):
                st.markdown(f"### {batch.get('batch_code', 'Lote')}")
                st.caption(
                    f"{_product_name(str(batch.get('product_id', '')), products)} · "
                    f"{_variant_name(str(batch.get('variant_id', '')), variants)} · "
                    f"Producción {batch.get('production_id', '')}"
                )
                columns = st.columns(5)
                columns[0].metric("Producido", f"{_num(batch.get('produced_quantity')):,.2f}")
                columns[1].metric("Aprobado", f"{_num(batch.get('accepted_quantity')):,.2f}")
                columns[2].metric("Rechazado", f"{_num(batch.get('rejected_quantity')):,.2f}")
                columns[3].metric("Costo rechazado", format_money(_num(batch.get("rejected_cost"))))
                columns[4].metric("Calidad", str(batch.get("quality_status", "")))
                if batch.get("defects"):
                    st.write(f"**Defectos:** {', '.join(str(item) for item in batch.get('defects', []))}")
                if batch.get("notes"):
                    st.write(str(batch.get("notes")))

    render_info_card(
        "Producción controlada",
        "Cada lote conserva producto, variante, resultado de calidad, merma, responsable y existencias aprobadas.",
        "TRAZABILIDAD",
    )
