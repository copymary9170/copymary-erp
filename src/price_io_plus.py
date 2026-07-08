"""Importación y exportación avanzada de precios."""

from datetime import date, datetime, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


PRICE_HEADERS = [
    "ID", "Origen", "Producto o servicio", "Categoría", "Moneda", "Costo unitario",
    "Precio de venta", "Margen (%)", "Material", "Equipo", "Activo", "Notas",
]
CATALOG_HEADERS = [
    "ID", "SKU", "Nombre", "Tipo", "Categoría", "Precio de venta", "Costo unitario", "Activo", "Notas",
]


def _activate_backup() -> None:
    for section, label in (
        ("price_import_history", "Historial de importación de precios"),
        ("price_export_history", "Historial de exportación de precios"),
        ("price_import_staging", "Prevalidación de precios importados"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, rows: list[dict]) -> None:
    st.session_state[key] = rows


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def _margin(price: float, cost: float) -> float:
    return ((price - cost) / price * 100.0) if price > 0 else 0.0


def _money(value: float, currency: str | None = None) -> str:
    return format_money(value, currency or get_currency())


def _price_rows(include_catalog: bool = True, include_saved: bool = True) -> list[dict]:
    rows: list[dict] = []
    if include_saved:
        for price in _rows("saved_prices"):
            rows.append({
                "source": "Costeo",
                "id": str(price.get("price_id", "")),
                "name": str(price.get("name", "Producto o servicio")),
                "category": str(price.get("category", "Sin categoría")),
                "currency": str(price.get("currency", get_currency())),
                "unit_cost": _num(price.get("unit_cost")),
                "unit_price": _num(price.get("unit_price")),
                "profit_margin": _num(price.get("profit_margin"), _margin(_num(price.get("unit_price")), _num(price.get("unit_cost")))),
                "material_label": str(price.get("material_label", "Costo manual")),
                "asset_label": str(price.get("asset_label", "Sin equipo registrado")),
                "active": True,
                "notes": str(price.get("notes", "")),
            })
    if include_catalog:
        for product in _rows("products_registry"):
            cost = _num(product.get("costing_unit_cost", product.get("calculated_cost", 0.0)))
            price = _num(product.get("sale_price"))
            rows.append({
                "source": "Catálogo",
                "id": str(product.get("product_id", "")),
                "sku": str(product.get("sku", "")),
                "name": str(product.get("name", "Producto")),
                "product_type": str(product.get("product_type", "Producto")),
                "category": str(product.get("category", "Sin categoría")),
                "currency": get_currency(),
                "unit_cost": cost,
                "unit_price": price,
                "profit_margin": _margin(price, cost),
                "material_label": "Receta/Catálogo",
                "asset_label": "",
                "active": bool(product.get("active", True)),
                "notes": str(product.get("notes", "")),
            })
    return rows


def _build_prices_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(PRICE_HEADERS)
    for row in rows:
        writer.writerow([
            row.get("id", ""), row.get("source", ""), row.get("name", ""), row.get("category", ""), row.get("currency", get_currency()),
            f"{_num(row.get('unit_cost')):.4f}", f"{_num(row.get('unit_price')):.4f}", f"{_num(row.get('profit_margin')):.2f}",
            row.get("material_label", ""), row.get("asset_label", ""), "Sí" if row.get("active", True) else "No", row.get("notes", ""),
        ])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _build_catalog_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(CATALOG_HEADERS)
    for row in rows:
        if row.get("source") != "Catálogo":
            continue
        writer.writerow([
            row.get("id", ""), row.get("sku", ""), row.get("name", ""), row.get("product_type", "Producto"), row.get("category", ""),
            f"{_num(row.get('unit_price')):.4f}", f"{_num(row.get('unit_cost')):.4f}", "Sí" if row.get("active", True) else "No", row.get("notes", ""),
        ])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _build_template() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(PRICE_HEADERS)
    writer.writerow(["", "Costeo", "Ejemplo impresión color", "Impresión", get_currency(), "0.1200", "0.2500", "52.00", "Papel bond", "HP 580", "Sí", "Editar o borrar esta fila"])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _parse_import(file_bytes: bytes) -> tuple[list[dict], list[str]]:
    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = file_bytes.decode("latin-1")
    reader = csv.DictReader(io.StringIO(decoded), delimiter=";")
    headers = reader.fieldnames or []
    missing = [header for header in PRICE_HEADERS if header not in headers]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias: {', '.join(missing)}")
    imported: list[dict] = []
    errors: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        name = str(row.get("Producto o servicio", "")).strip()
        source = str(row.get("Origen", "Costeo")).strip() or "Costeo"
        price = _num(row.get("Precio de venta"))
        cost = _num(row.get("Costo unitario"))
        currency = str(row.get("Moneda", get_currency())).strip().upper() or get_currency()
        if not name:
            errors.append(f"Fila {row_number}: falta el nombre.")
        if source not in {"Costeo", "Catálogo"}:
            errors.append(f"Fila {row_number}: origen inválido.")
        if price <= 0:
            errors.append(f"Fila {row_number}: precio de venta debe ser mayor que cero.")
        if cost < 0:
            errors.append(f"Fila {row_number}: costo unitario no puede ser negativo.")
        if currency not in {"USD", "VES", "EUR"}:
            errors.append(f"Fila {row_number}: moneda inválida.")
        imported.append({
            "source": source,
            "id": str(row.get("ID", "")).strip() or uuid4().hex[:8],
            "name": name or "Producto sin nombre",
            "category": str(row.get("Categoría", "Sin categoría")).strip() or "Sin categoría",
            "currency": currency,
            "unit_cost": cost,
            "unit_price": price,
            "profit_margin": _num(row.get("Margen (%)"), _margin(price, cost)),
            "material_label": str(row.get("Material", "Costo manual")).strip() or "Costo manual",
            "asset_label": str(row.get("Equipo", "Sin equipo registrado")).strip() or "Sin equipo registrado",
            "active": str(row.get("Activo", "Sí")).strip().casefold() not in {"no", "false", "0", "inactivo"},
            "notes": str(row.get("Notas", "")).strip(),
            "row_number": row_number,
        })
    if not imported:
        raise ValueError("El archivo no contiene filas importables.")
    return imported, errors


def _apply_import(imported: list[dict], mode: str) -> None:
    saved = _rows("saved_prices")
    products = _rows("products_registry")
    if mode == "Reemplazar precios de costeo":
        saved = []
    if mode == "Reemplazar catálogo":
        products = []
    saved_by_id = {str(row.get("price_id", "")): dict(row) for row in saved if row.get("price_id")}
    products_by_id = {str(row.get("product_id", "")): dict(row) for row in products if row.get("product_id")}

    for row in imported:
        if row.get("source") == "Catálogo":
            current = products_by_id.get(str(row.get("id")), {})
            current.update({
                "product_id": str(row.get("id")),
                "sku": str(current.get("sku", "")),
                "name": str(row.get("name")),
                "product_type": str(current.get("product_type", "Producto")),
                "category": str(row.get("category")),
                "sale_price": _num(row.get("unit_price")),
                "costing_unit_cost": _num(row.get("unit_cost")),
                "active": bool(row.get("active", True)),
                "notes": str(row.get("notes", "")),
                "imported_at_utc": _now(),
            })
            products_by_id[str(row.get("id"))] = current
        else:
            current = saved_by_id.get(str(row.get("id")), {})
            current.update({
                "price_id": str(row.get("id")),
                "name": str(row.get("name")),
                "category": str(row.get("category")),
                "currency": str(row.get("currency")),
                "profit_margin": _num(row.get("profit_margin")),
                "unit_cost": _num(row.get("unit_cost")),
                "unit_price": _num(row.get("unit_price")),
                "material_label": str(row.get("material_label")),
                "asset_label": str(row.get("asset_label")),
                "notes": str(row.get("notes", "")),
                "imported_at_utc": _now(),
            })
            saved_by_id[str(row.get("id"))] = current

    _save("saved_prices", list(saved_by_id.values()))
    _save("products_registry", list(products_by_id.values()))


def render_price_io_plus() -> None:
    render_page_header(
        "Importar y exportar precios",
        "Gestiona plantillas, validación previa, respaldo y exportación separada de costeo y catálogo.",
    )

    rows = _price_rows()
    import_history = _rows("price_import_history")
    export_history = _rows("price_export_history")

    metrics = st.columns(5)
    metrics[0].metric("Precios totales", str(len(rows)))
    metrics[1].metric("Catálogo", str(sum(1 for row in rows if row.get("source") == "Catálogo")))
    metrics[2].metric("Costeo", str(sum(1 for row in rows if row.get("source") == "Costeo")))
    metrics[3].metric("Importaciones", str(len(import_history)))
    metrics[4].metric("Exportaciones", str(len(export_history)))

    import_tab, export_tab, template_tab, audit_tab = st.tabs(("Importar", "Exportar", "Plantilla", "Auditoría"))

    with import_tab:
        uploaded_file = st.file_uploader("CSV de precios", type=("csv",), accept_multiple_files=False)
        mode = st.radio("Modo", ("Combinar por ID", "Reemplazar precios de costeo", "Reemplazar catálogo"), horizontal=True)
        if uploaded_file is not None and st.button("Validar archivo", type="primary", use_container_width=True):
            try:
                imported, errors = _parse_import(uploaded_file.getvalue())
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["price_import_preview"] = {"rows": imported, "errors": errors, "mode": mode, "file_name": uploaded_file.name}
                st.rerun()

        preview = st.session_state.get("price_import_preview")
        if isinstance(preview, dict):
            imported = [dict(row) for row in preview.get("rows", [])]
            errors = [str(error) for error in preview.get("errors", [])]
            st.markdown("#### Prevalidación")
            cols = st.columns(4)
            cols[0].metric("Filas", str(len(imported)))
            cols[1].metric("Errores", str(len(errors)))
            cols[2].metric("Costeo", str(sum(1 for row in imported if row.get("source") == "Costeo")))
            cols[3].metric("Catálogo", str(sum(1 for row in imported if row.get("source") == "Catálogo")))
            for error in errors[:20]:
                st.error(error)
            for row in imported[:50]:
                with st.container(border=True):
                    columns = st.columns([3, 1, 1, 1])
                    columns[0].markdown(f"**{row.get('name', 'Producto')}**")
                    columns[0].caption(f"Fila {row.get('row_number')} · {row.get('source')} · {row.get('category')}")
                    columns[1].metric("Costo", _money(_num(row.get("unit_cost")), str(row.get("currency", get_currency()))))
                    columns[2].metric("Precio", _money(_num(row.get("unit_price")), str(row.get("currency", get_currency()))))
                    columns[3].metric("Margen", f"{_margin(_num(row.get('unit_price')), _num(row.get('unit_cost'))):,.1f}%")
            if st.button("Aplicar importación validada", type="primary", use_container_width=True, disabled=bool(errors)):
                _apply_import(imported, str(preview.get("mode", "Combinar por ID")))
                import_history.append({
                    "import_id": f"IMP-{uuid4().hex[:8].upper()}",
                    "file_name": str(preview.get("file_name", "archivo.csv")),
                    "mode": str(preview.get("mode", "Combinar por ID")),
                    "rows": len(imported),
                    "created_at_utc": _now(),
                })
                _save("price_import_history", import_history)
                st.session_state.pop("price_import_preview", None)
                st.success("Importación aplicada.")
                st.rerun()

    with export_tab:
        source_filter = st.selectbox("Origen", ("Todos", "Costeo", "Catálogo"))
        only_active = st.checkbox("Solo activos", value=True)
        export_rows = [
            row for row in rows
            if (source_filter == "Todos" or row.get("source") == source_filter)
            and (not only_active or row.get("active", True))
        ]
        st.download_button(
            "Descargar CSV completo",
            data=_build_prices_csv(export_rows),
            file_name=f"copymary_precios_completo_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not export_rows,
        )
        st.download_button(
            "Descargar CSV solo catálogo",
            data=_build_catalog_csv(export_rows),
            file_name=f"copymary_precios_catalogo_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not any(row.get("source") == "Catálogo" for row in export_rows),
        )
        if st.button("Registrar exportación en auditoría", use_container_width=True, disabled=not export_rows):
            export_history.append({
                "export_id": f"EXP-{uuid4().hex[:8].upper()}",
                "source_filter": source_filter,
                "only_active": bool(only_active),
                "rows": len(export_rows),
                "created_at_utc": _now(),
            })
            _save("price_export_history", export_history)
            st.rerun()

        for row in export_rows[:100]:
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row.get('name', 'Producto')}**")
                cols[0].caption(f"{row.get('source')} · {row.get('category')} · ID {row.get('id')}")
                cols[1].metric("Costo", _money(_num(row.get("unit_cost")), str(row.get("currency", get_currency()))))
                cols[2].metric("Precio", _money(_num(row.get("unit_price")), str(row.get("currency", get_currency()))))
                cols[3].metric("Margen", f"{_margin(_num(row.get('unit_price')), _num(row.get('unit_cost'))):,.1f}%")

    with template_tab:
        st.download_button(
            "Descargar plantilla editable",
            data=_build_template(),
            file_name="plantilla_importar_precios_copymary.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )
        render_info_card(
            "Columnas obligatorias",
            "ID, Origen, Producto o servicio, Categoría, Moneda, Costo unitario, Precio de venta, Margen, Material, Equipo, Activo y Notas.",
            "PLANTILLA",
        )

    with audit_tab:
        st.markdown("#### Importaciones")
        if not import_history:
            st.info("No hay importaciones registradas.")
        for row in reversed(import_history[-100:]):
            st.write(f"**{row.get('import_id', '')}** · {row.get('file_name', '')} · {row.get('rows', 0)} fila(s) · {row.get('created_at_utc', '')}")
        st.markdown("#### Exportaciones")
        if not export_history:
            st.info("No hay exportaciones registradas.")
        for row in reversed(export_history[-100:]):
            st.write(f"**{row.get('export_id', '')}** · {row.get('source_filter', '')} · {row.get('rows', 0)} fila(s) · {row.get('created_at_utc', '')}")

    render_info_card(
        "Intercambio controlado",
        "La importación valida antes de aplicar y la exportación deja rastro en auditoría para proteger listas de precios.",
        "PRECIOS",
    )


app_shell.FUNCTIONAL_MODULES["Exportar precios"] = render_price_io_plus
