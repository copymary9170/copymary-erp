"""Acciones masivas y restauración para mantenimiento del catálogo."""

from collections import Counter
from datetime import datetime, timezone

import streamlit as st

from src import catalog_maintenance as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money


def _activate_backup() -> None:
    section = "catalog_bulk_actions"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Acciones masivas del catálogo"
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


def _record(action: str, details: str, count: int, responsible: str) -> None:
    rows = _rows("catalog_bulk_actions")
    rows.append({
        "action": action,
        "details": details,
        "affected_records": count,
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("catalog_bulk_actions", rows)


def render_catalog_maintenance_bulk() -> None:
    render_page_header(
        "Mantenimiento del catálogo",
        "Aplica cambios controlados, restaura versiones y normaliza el catálogo.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_catalog_maintenance()
    finally:
        base.render_page_header = original_header

    products = _rows("products_registry")
    versions = _rows("catalog_recipe_versions")
    actions = _rows("catalog_bulk_actions")
    categories = sorted({str(item.get("category", "Otro")).strip() or "Otro" for item in products})

    st.divider()
    metrics = st.columns(4)
    metrics[0].metric("Categorías", str(len(categories)))
    metrics[1].metric("Activos", str(sum(1 for item in products if item.get("active", True))))
    metrics[2].metric("Archivados", str(sum(1 for item in products if not item.get("active", True))))
    metrics[3].metric("Acciones masivas", str(len(actions)))

    restore_tab, prices_tab, archive_tab, categories_tab, audit_tab = st.tabs(
        ("Restaurar versión", "Precios masivos", "Archivo masivo", "Categorías", "Auditoría")
    )

    with restore_tab:
        options = {
            f"{item.get('name', 'Producto')} · {item.get('product_id', '')}": str(item.get("product_id", ""))
            for item in products
        }
        if not options:
            st.info("No hay productos disponibles.")
        else:
            selected = st.selectbox("Producto", tuple(options.keys()), key="restore_catalog_product")
            product_id = options[selected]
            available = [item for item in versions if str(item.get("product_id", "")) == product_id]
            if not available:
                st.info("Este producto todavía no tiene versiones guardadas.")
            else:
                version_options = {
                    f"Versión {item.get('version_number', '')} · {str(item.get('created_at_utc', ''))[:10]} · {format_money(_num(item.get('sale_price')))}": str(item.get("version_id", ""))
                    for item in reversed(available)
                }
                selected_version = st.selectbox("Versión", tuple(version_options.keys()))
                version = next(item for item in available if str(item.get("version_id", "")) == version_options[selected_version])
                with st.form("restore_catalog_version_form"):
                    responsible = st.text_input("Responsable")
                    reason = st.text_area("Motivo", max_chars=400)
                    confirmed = st.checkbox("Confirmo la restauración")
                    submitted = st.form_submit_button("Restaurar", type="primary", use_container_width=True)
                if submitted:
                    if not confirmed or not reason.strip():
                        st.error("Confirma la acción e indica el motivo.")
                    else:
                        updated = []
                        for product in products:
                            row = dict(product)
                            if str(row.get("product_id", "")) == product_id:
                                row["recipe"] = [dict(item) for item in version.get("recipe", []) if isinstance(item, dict)]
                                row["sale_price"] = _num(version.get("sale_price"))
                                row["extra_cost"] = _num(version.get("extra_cost"))
                                row["updated_at_utc"] = _now()
                                row["last_reviewed_at_utc"] = _now()
                            updated.append(row)
                        _save("products_registry", updated)
                        base._log(product_id, "Restauración", reason, responsible)
                        st.rerun()

    with prices_tab:
        if not products:
            st.info("No hay productos para ajustar.")
        else:
            with st.form("bulk_catalog_prices"):
                columns = st.columns(4)
                category = columns[0].selectbox("Categoría", ("Todas", *categories))
                product_type = columns[1].selectbox("Tipo", ("Todos", "Producto", "Servicio"))
                operation = columns[2].selectbox("Operación", ("Aumentar %", "Reducir %", "Sumar monto", "Restar monto"))
                value = columns[3].number_input("Valor", min_value=0.0, value=0.0, step=0.5)
                responsible = st.text_input("Responsable")
                confirmed = st.checkbox("Confirmo el ajuste masivo")
                submitted = st.form_submit_button("Aplicar", type="primary", use_container_width=True)
            if submitted:
                targets = [
                    item for item in products
                    if (category == "Todas" or str(item.get("category", "Otro")) == category)
                    and (product_type == "Todos" or str(item.get("product_type", "")) == product_type)
                ]
                if value <= 0 or not confirmed:
                    st.error("Indica un valor mayor que cero y confirma la acción.")
                elif not targets:
                    st.error("No hay registros que coincidan con los filtros.")
                else:
                    target_ids = {str(item.get("product_id", "")) for item in targets}
                    updated = []
                    for product in products:
                        row = dict(product)
                        if str(row.get("product_id", "")) in target_ids:
                            current = _num(row.get("sale_price"))
                            if operation == "Aumentar %":
                                new_value = current * (1 + value / 100)
                            elif operation == "Reducir %":
                                new_value = current * (1 - value / 100)
                            elif operation == "Sumar monto":
                                new_value = current + value
                            else:
                                new_value = current - value
                            row["sale_price"] = max(round(new_value, 4), 0.01)
                            row["updated_at_utc"] = _now()
                        updated.append(row)
                    _save("products_registry", updated)
                    _record("Precios masivos", f"{operation}: {value} · {category} · {product_type}", len(targets), responsible)
                    st.rerun()

    with archive_tab:
        with st.form("bulk_catalog_archive"):
            category = st.selectbox("Categoría", ("Todas", *categories), key="archive_category")
            action = st.selectbox("Acción", ("Archivar", "Reactivar"))
            responsible = st.text_input("Responsable")
            confirmed = st.checkbox("Confirmo la acción masiva")
            submitted = st.form_submit_button("Aplicar", type="primary", use_container_width=True)
        if submitted:
            targets = [item for item in products if category == "Todas" or str(item.get("category", "Otro")) == category]
            if not confirmed:
                st.error("Debes confirmar la acción.")
            elif not targets:
                st.error("No hay registros para modificar.")
            else:
                target_ids = {str(item.get("product_id", "")) for item in targets}
                updated = []
                for product in products:
                    row = dict(product)
                    if str(row.get("product_id", "")) in target_ids:
                        row["active"] = action == "Reactivar"
                        row["updated_at_utc"] = _now()
                    updated.append(row)
                _save("products_registry", updated)
                _record(action, f"Categoría: {category}", len(targets), responsible)
                st.rerun()

    with categories_tab:
        counts = Counter(str(item.get("category", "Otro")).strip() or "Otro" for item in products)
        for category, count in counts.most_common():
            st.write(f"**{category}:** {count} registro(s)")
        if categories:
            with st.form("normalize_catalog_category"):
                source = st.selectbox("Categoría actual", tuple(categories))
                destination = st.text_input("Nueva categoría")
                responsible = st.text_input("Responsable")
                confirmed = st.checkbox("Confirmo el cambio")
                submitted = st.form_submit_button("Renombrar categoría", type="primary", use_container_width=True)
            if submitted:
                targets = [item for item in products if str(item.get("category", "Otro")) == source]
                if not destination.strip() or not confirmed:
                    st.error("Indica la nueva categoría y confirma la acción.")
                else:
                    updated = []
                    for product in products:
                        row = dict(product)
                        if str(row.get("category", "Otro")) == source:
                            row["category"] = destination.strip()
                            row["updated_at_utc"] = _now()
                        updated.append(row)
                    _save("products_registry", updated)
                    _record("Categoría renombrada", f"{source} → {destination.strip()}", len(targets), responsible)
                    st.rerun()

    with audit_tab:
        if not actions:
            st.info("No hay acciones masivas registradas.")
        for action in reversed(actions[-100:]):
            with st.container(border=True):
                columns = st.columns([3, 1])
                columns[0].markdown(f"**{action.get('action', 'Acción')}**")
                columns[0].write(str(action.get("details", "")))
                columns[1].metric("Registros", str(action.get("affected_records", 0)))
                st.caption(f"{action.get('created_at_utc', '')} · {action.get('responsible', 'Sin asignar')}")

    render_info_card(
        "Mantenimiento gobernado",
        "Restauraciones y acciones masivas quedan registradas para conservar trazabilidad.",
        "CONTROL DEL CATÁLOGO",
    )
