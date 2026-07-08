"""Gobierno adicional para importación y exportación de precios."""

from collections import Counter
from datetime import date, datetime, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, price_io_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("price_io_snapshots", "Instantáneas de precios"),
        ("price_io_conflicts", "Conflictos de importación de precios"),
        ("price_io_templates", "Plantillas de intercambio de precios"),
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
        return float(value)
    except (TypeError, ValueError):
        return default


def _price_rows() -> list[dict]:
    return base._price_rows()


def _row_key(row: dict) -> str:
    return f"{row.get('source', '')}::{row.get('id', '')}"


def _build_snapshot_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(base.PRICE_HEADERS)
    for row in rows:
        writer.writerow([
            row.get("id", ""), row.get("source", ""), row.get("name", ""), row.get("category", ""), row.get("currency", get_currency()),
            f"{_num(row.get('unit_cost')):.4f}", f"{_num(row.get('unit_price')):.4f}", f"{_num(row.get('profit_margin')):.2f}",
            row.get("material_label", ""), row.get("asset_label", ""), "Sí" if row.get("active", True) else "No", row.get("notes", ""),
        ])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _compare_import(imported: list[dict], current: list[dict]) -> list[dict]:
    current_by_key = {_row_key(row): row for row in current}
    report: list[dict] = []
    seen = Counter(_row_key(row) for row in imported)
    for row in imported:
        key = _row_key(row)
        existing = current_by_key.get(key)
        old_price = _num(existing.get("unit_price")) if existing else 0.0
        new_price = _num(row.get("unit_price"))
        old_cost = _num(existing.get("unit_cost")) if existing else 0.0
        new_cost = _num(row.get("unit_cost"))
        change = new_price - old_price
        change_percent = change / old_price * 100.0 if old_price > 0 else 0.0
        status = "Nuevo" if existing is None else "Actualiza" if abs(change) > 0.0001 or abs(new_cost - old_cost) > 0.0001 else "Sin cambio"
        risk = []
        if seen[key] > 1:
            risk.append("ID duplicado en archivo")
        if new_cost > 0 and new_price < new_cost:
            risk.append("Precio bajo costo")
        if abs(change_percent) >= 25 and existing is not None:
            risk.append("Cambio mayor a 25%")
        if str(row.get("name", "")).strip().casefold() != str((existing or {}).get("name", "")).strip().casefold() and existing is not None:
            risk.append("Nombre distinto para el mismo ID")
        report.append({
            **row,
            "status": status,
            "old_price": old_price,
            "new_price": new_price,
            "old_cost": old_cost,
            "new_cost": new_cost,
            "change": change,
            "change_percent": change_percent,
            "risk": ", ".join(risk),
            "blocked": bool(risk),
        })
    return report


def _export_report(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Estado", "Origen", "ID", "Nombre", "Precio anterior", "Precio nuevo", "Variación", "Variación %", "Riesgo"])
    for row in rows:
        writer.writerow([
            row.get("status", ""), row.get("source", ""), row.get("id", ""), row.get("name", ""),
            row.get("old_price", 0), row.get("new_price", 0), row.get("change", 0), row.get("change_percent", 0), row.get("risk", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def _restore_snapshot(snapshot: dict) -> None:
    saved_prices = []
    products = []
    for row in snapshot.get("rows", []):
        current = dict(row)
        if current.get("source") == "Catálogo":
            products.append({
                "product_id": current.get("id", uuid4().hex[:8]),
                "sku": current.get("sku", ""),
                "name": current.get("name", "Producto"),
                "product_type": current.get("product_type", "Producto"),
                "category": current.get("category", "Sin categoría"),
                "sale_price": _num(current.get("unit_price")),
                "costing_unit_cost": _num(current.get("unit_cost")),
                "active": bool(current.get("active", True)),
                "notes": current.get("notes", ""),
                "restored_at_utc": _now(),
            })
        else:
            saved_prices.append({
                "price_id": current.get("id", uuid4().hex[:8]),
                "name": current.get("name", "Producto o servicio"),
                "category": current.get("category", "Sin categoría"),
                "currency": current.get("currency", get_currency()),
                "profit_margin": _num(current.get("profit_margin")),
                "unit_cost": _num(current.get("unit_cost")),
                "unit_price": _num(current.get("unit_price")),
                "material_label": current.get("material_label", "Costo manual"),
                "asset_label": current.get("asset_label", "Sin equipo registrado"),
                "notes": current.get("notes", ""),
                "restored_at_utc": _now(),
            })
    _save("saved_prices", saved_prices)
    _save("products_registry", products)


def render_price_io_governance() -> None:
    render_page_header(
        "Importar y exportar precios",
        "Añade conciliación, conflictos, instantáneas y restauración segura de listas de precios.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_price_io_plus()
    finally:
        base.render_page_header = original_header

    rows = _price_rows()
    snapshots = _rows("price_io_snapshots")
    conflicts = _rows("price_io_conflicts")
    templates = _rows("price_io_templates")

    st.divider()
    st.markdown("### Control adicional de intercambio")
    metrics = st.columns(5)
    metrics[0].metric("Precios activos", str(len(rows)))
    metrics[1].metric("Instantáneas", str(len(snapshots)))
    metrics[2].metric("Conflictos", str(len(conflicts)))
    metrics[3].metric("Plantillas", str(len(templates)))
    metrics[4].metric("Valor lista", format_money(sum(_num(row.get("unit_price")) for row in rows), get_currency()))

    reconcile_tab, snapshot_tab, template_tab = st.tabs(("Conciliar importación", "Instantáneas", "Plantillas internas"))

    with reconcile_tab:
        uploaded = st.file_uploader("Archivo para conciliación", type=("csv",), key="reconcile_price_file")
        if uploaded is not None and st.button("Comparar contra lista actual", type="primary", use_container_width=True):
            try:
                imported, errors = base._parse_import(uploaded.getvalue())
            except ValueError as exc:
                st.error(str(exc))
            else:
                report = _compare_import(imported, rows)
                st.session_state["price_reconcile_report"] = {"rows": report, "errors": errors, "file_name": uploaded.name}
                st.rerun()

        report_data = st.session_state.get("price_reconcile_report")
        if isinstance(report_data, dict):
            report = [dict(row) for row in report_data.get("rows", [])]
            errors = [str(error) for error in report_data.get("errors", [])]
            blocked = [row for row in report if row.get("blocked")]
            new_rows = [row for row in report if row.get("status") == "Nuevo"]
            updated = [row for row in report if row.get("status") == "Actualiza"]
            cols = st.columns(5)
            cols[0].metric("Filas", str(len(report)))
            cols[1].metric("Nuevos", str(len(new_rows)))
            cols[2].metric("Actualiza", str(len(updated)))
            cols[3].metric("Bloqueados", str(len(blocked)))
            cols[4].metric("Errores", str(len(errors)))
            for error in errors[:20]:
                st.error(error)
            st.download_button(
                "Descargar conciliación CSV",
                data=_export_report(report),
                file_name=f"conciliacion_precios_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
            for row in report[:100]:
                with st.container(border=True):
                    cols = st.columns([3, 1, 1, 1])
                    cols[0].markdown(f"**{row.get('name', 'Producto')} · {row.get('status', '')}**")
                    cols[0].caption(f"{row.get('source')} · {row.get('id')} · {row.get('risk') or 'Sin riesgo'}")
                    cols[1].metric("Anterior", format_money(_num(row.get("old_price")), str(row.get("currency", get_currency()))))
                    cols[2].metric("Nuevo", format_money(_num(row.get("new_price")), str(row.get("currency", get_currency()))))
                    cols[3].metric("Cambio", f"{_num(row.get('change_percent')):+,.1f}%")
            if blocked:
                if st.button("Registrar conflictos detectados", use_container_width=True):
                    for row in blocked:
                        conflicts.append({
                            "conflict_id": f"CF-{uuid4().hex[:8].upper()}",
                            "file_name": str(report_data.get("file_name", "archivo.csv")),
                            "source": row.get("source", ""),
                            "source_id": row.get("id", ""),
                            "name": row.get("name", ""),
                            "risk": row.get("risk", ""),
                            "status": "Pendiente",
                            "created_at_utc": _now(),
                        })
                    _save("price_io_conflicts", conflicts)
                    st.rerun()

    with snapshot_tab:
        with st.form("price_snapshot_form", clear_on_submit=True):
            name = st.text_input("Nombre de la instantánea", placeholder="Antes de importar lista julio")
            note = st.text_input("Nota")
            submitted = st.form_submit_button("Crear instantánea", type="primary", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("Indica un nombre.")
            else:
                snapshots.append({
                    "snapshot_id": f"SNP-{uuid4().hex[:8].upper()}",
                    "name": name.strip(),
                    "note": note.strip(),
                    "rows": rows,
                    "count": len(rows),
                    "created_at_utc": _now(),
                })
                _save("price_io_snapshots", snapshots)
                st.rerun()
        for snapshot in reversed(snapshots[-50:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{snapshot.get('name', 'Instantánea')} · {snapshot.get('snapshot_id', '')}**")
                cols[0].caption(f"{snapshot.get('note', '')} · {snapshot.get('created_at_utc', '')}")
                cols[1].metric("Precios", str(snapshot.get("count", 0)))
                if cols[2].button("Restaurar", key=f"restore_snapshot_{snapshot.get('snapshot_id')}", use_container_width=True):
                    _restore_snapshot(snapshot)
                    st.success("Instantánea restaurada.")
                    st.rerun()
                st.download_button(
                    "Descargar instantánea CSV",
                    data=_build_snapshot_csv([dict(row) for row in snapshot.get("rows", [])]),
                    file_name=f"snapshot_precios_{snapshot.get('snapshot_id', 'sin_id')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    with template_tab:
        with st.form("price_template_save_form", clear_on_submit=True):
            template_name = st.text_input("Nombre de plantilla interna")
            description = st.text_input("Descripción")
            submitted = st.form_submit_button("Guardar plantilla actual", type="primary", use_container_width=True)
        if submitted:
            if not template_name.strip():
                st.error("Indica un nombre.")
            else:
                templates.append({
                    "template_id": f"TPL-{uuid4().hex[:8].upper()}",
                    "name": template_name.strip(),
                    "description": description.strip(),
                    "rows": rows,
                    "created_at_utc": _now(),
                })
                _save("price_io_templates", templates)
                st.rerun()
        if not templates:
            st.info("No hay plantillas internas guardadas.")
        for template in reversed(templates[-50:]):
            st.write(f"**{template.get('name', 'Plantilla')}** · {len(template.get('rows', []))} precio(s) · {template.get('description', '')}")

    render_info_card(
        "Importación segura",
        "Antes de cambiar precios puedes comparar, guardar una instantánea y restaurar si algo sale mal.",
        "CONTROL DE DATOS",
    )


app_shell.FUNCTIONAL_MODULES["Exportar precios"] = render_price_io_governance
