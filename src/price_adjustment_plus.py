"""Ajustes de precios con vista previa, reglas y trazabilidad."""

from datetime import date, datetime, timezone
from uuid import uuid4
import csv
import io
import math

import streamlit as st

from src import app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("price_adjustment_batches", "Lotes de ajustes de precios"),
        ("price_adjustment_history", "Historial de ajustes de precios"),
        ("price_floor_rules", "Reglas de precio mínimo"),
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


ROUNDING_OPTIONS = {
    "Sin redondeo": 0.0,
    "Al siguiente 0,05": 0.05,
    "Al siguiente 0,10": 0.10,
    "Al siguiente 0,25": 0.25,
    "Al siguiente 0,50": 0.50,
    "Al siguiente 1,00": 1.00,
    "Al siguiente 5,00": 5.00,
    "Al siguiente 10,00": 10.00,
}


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


def _round_up(value: float, increment: float) -> float:
    if increment <= 0:
        return value
    return math.ceil((value - 1e-12) / increment) * increment


def _margin(price: float, cost: float) -> float:
    return ((price - cost) / price * 100.0) if price > 0 else 0.0


def _minimum_price(cost: float, margin_percent: float) -> float:
    margin = min(max(margin_percent / 100.0, 0.0), 0.95)
    return cost / max(1.0 - margin, 0.05)


def _source_rows() -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for price in _rows("saved_prices"):
        key = f"saved::{price.get('price_id', '')}"
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "source": "Costeo",
            "source_id": str(price.get("price_id", "")),
            "name": str(price.get("name", "Producto o servicio")),
            "category": str(price.get("category", "Sin categoría")),
            "currency": str(price.get("currency", get_currency())),
            "unit_cost": _num(price.get("unit_cost")),
            "current_price": _num(price.get("unit_price")),
            "active": True,
        })
    for product in _rows("products_registry"):
        key = f"catalog::{product.get('product_id', '')}"
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "source": "Catálogo",
            "source_id": str(product.get("product_id", "")),
            "name": str(product.get("name", "Producto")),
            "category": str(product.get("category", "Sin categoría")),
            "currency": get_currency(),
            "unit_cost": _num(product.get("costing_unit_cost", product.get("calculated_cost", 0.0))),
            "current_price": _num(product.get("sale_price")),
            "active": bool(product.get("active", True)),
        })
    return rows


def _floor_for(row: dict, rules: list[dict]) -> float:
    candidates = [
        rule for rule in rules
        if rule.get("active", True)
        and (
            str(rule.get("scope", "General")) == "General"
            or (str(rule.get("scope")) == "Categoría" and str(rule.get("value", "")) == str(row.get("category", "")))
            or (str(rule.get("scope")) == "Producto" and str(rule.get("value", "")) == str(row.get("source_id", "")))
        )
    ]
    return max((_num(rule.get("minimum_price")) for rule in candidates), default=0.0)


def _adjust(row: dict, method: str, value: float, increment: float, margin_floor: float, absolute_floor: float) -> dict:
    current = _num(row.get("current_price"))
    cost = _num(row.get("unit_cost"))
    if method == "Aumentar porcentaje":
        proposed = current * (1.0 + value / 100.0)
    elif method == "Reducir porcentaje":
        proposed = current * (1.0 - value / 100.0)
    elif method == "Aumentar monto":
        proposed = current + value
    elif method == "Fijar precio":
        proposed = value
    else:
        proposed = current
    protected_floor = max(absolute_floor, _minimum_price(cost, margin_floor) if cost > 0 else 0.0)
    adjusted = _round_up(max(proposed, protected_floor, 0.0), increment)
    return {
        **row,
        "proposed_price": proposed,
        "protected_floor": protected_floor,
        "adjusted_price": adjusted,
        "difference": adjusted - current,
        "effective_margin": _margin(adjusted, cost),
        "blocked": proposed < protected_floor,
    }


def _apply(rows: list[dict], responsible: str, reason: str, batch_id: str) -> None:
    saved_prices = _rows("saved_prices")
    products = _rows("products_registry")
    history = _rows("price_adjustment_history")

    adjusted_map = {(row.get("source"), row.get("source_id")): row for row in rows}

    updated_saved = []
    for price in saved_prices:
        current = dict(price)
        adjusted = adjusted_map.get(("Costeo", str(current.get("price_id", ""))))
        if adjusted:
            current["previous_unit_price"] = _num(current.get("unit_price"))
            current["unit_price"] = _num(adjusted.get("adjusted_price"))
            current["price_adjustment_batch_id"] = batch_id
            current["price_updated_at_utc"] = _now()
        updated_saved.append(current)

    updated_products = []
    for product in products:
        current = dict(product)
        adjusted = adjusted_map.get(("Catálogo", str(current.get("product_id", ""))))
        if adjusted:
            current["previous_sale_price"] = _num(current.get("sale_price"))
            current["sale_price"] = _num(adjusted.get("adjusted_price"))
            current["price_adjustment_batch_id"] = batch_id
            current["price_updated_at_utc"] = _now()
            current["price_updated_by"] = responsible.strip() or "Sin asignar"
        updated_products.append(current)

    for row in rows:
        history.append({
            "history_id": f"PAH-{uuid4().hex[:8].upper()}",
            "batch_id": batch_id,
            "source": row.get("source", ""),
            "source_id": row.get("source_id", ""),
            "name": row.get("name", ""),
            "previous_price": _num(row.get("current_price")),
            "new_price": _num(row.get("adjusted_price")),
            "difference": _num(row.get("difference")),
            "unit_cost": _num(row.get("unit_cost")),
            "effective_margin": _num(row.get("effective_margin")),
            "responsible": responsible.strip() or "Sin asignar",
            "reason": reason.strip(),
            "created_at_utc": _now(),
        })

    _save("saved_prices", updated_saved)
    _save("products_registry", updated_products)
    _save("price_adjustment_history", history)


def _export(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Origen", "ID", "Nombre", "Categoría", "Costo", "Precio actual", "Propuesto",
        "Piso protegido", "Precio final", "Diferencia", "Margen efectivo", "Bloqueado",
    ])
    for row in rows:
        writer.writerow([
            row.get("source", ""), row.get("source_id", ""), row.get("name", ""), row.get("category", ""),
            row.get("unit_cost", 0), row.get("current_price", 0), row.get("proposed_price", 0),
            row.get("protected_floor", 0), row.get("adjusted_price", 0), row.get("difference", 0),
            row.get("effective_margin", 0), "Sí" if row.get("blocked") else "No",
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_price_adjustment_plus() -> None:
    render_page_header(
        "Ajustar precios",
        "Ajusta precios por lote sin bajar del costo, del margen mínimo ni de los pisos comerciales definidos.",
    )

    source_rows = _source_rows()
    floors = _rows("price_floor_rules")
    batches = _rows("price_adjustment_batches")
    history = _rows("price_adjustment_history")

    if not source_rows:
        st.info("No hay precios guardados ni productos con precio en el catálogo.")
        return

    active_rows = [row for row in source_rows if row.get("active", True)]
    low_margin = [row for row in active_rows if _num(row.get("unit_cost")) > 0 and _margin(_num(row.get("current_price")), _num(row.get("unit_cost"))) < 20]
    below_cost = [row for row in active_rows if _num(row.get("current_price")) < _num(row.get("unit_cost"))]

    metrics = st.columns(5)
    metrics[0].metric("Precios disponibles", str(len(active_rows)))
    metrics[1].metric("Bajo costo", str(len(below_cost)))
    metrics[2].metric("Margen menor a 20%", str(len(low_margin)))
    metrics[3].metric("Lotes aplicados", str(len(batches)))
    metrics[4].metric("Reglas de piso", str(len(floors)))

    if below_cost:
        st.error(f"Hay {len(below_cost)} precio(s) por debajo de su costo registrado.")
    elif low_margin:
        st.warning(f"Hay {len(low_margin)} precio(s) con margen menor a 20%.")

    adjust_tab, floors_tab, consistency_tab, history_tab = st.tabs(("Ajuste masivo", "Pisos mínimos", "Consistencia", "Historial"))

    with adjust_tab:
        filters = st.columns(3)
        source_filter = filters[0].selectbox("Origen", ("Todos", "Costeo", "Catálogo"))
        categories = sorted({str(row.get("category", "Sin categoría")) for row in active_rows})
        category_filter = filters[1].selectbox("Categoría", ("Todas", *categories))
        query = filters[2].text_input("Buscar").strip().casefold()

        candidates = [
            row for row in active_rows
            if (source_filter == "Todos" or row.get("source") == source_filter)
            and (category_filter == "Todas" or row.get("category") == category_filter)
            and (not query or query in str(row.get("name", "")).casefold())
        ]

        with st.form("price_adjustment_form"):
            columns = st.columns(5)
            method = columns[0].selectbox("Método", ("Aumentar porcentaje", "Reducir porcentaje", "Aumentar monto", "Fijar precio"))
            value = columns[1].number_input("Valor", min_value=0.0, value=0.0, step=0.5)
            rounding_label = columns[2].selectbox("Redondeo", tuple(ROUNDING_OPTIONS.keys()), index=2)
            margin_floor = columns[3].number_input("Margen mínimo %", min_value=0.0, max_value=95.0, value=40.0, step=1.0)
            responsible = columns[4].text_input("Responsable")
            reason = st.text_area("Motivo del ajuste", max_chars=500)
            preview = st.form_submit_button("Generar vista previa", type="primary", use_container_width=True)

        if preview:
            adjusted = [
                _adjust(row, method, float(value), ROUNDING_OPTIONS[rounding_label], float(margin_floor), _floor_for(row, floors))
                for row in candidates
            ]
            st.session_state["price_adjustment_preview"] = {
                "rows": adjusted,
                "method": method,
                "value": float(value),
                "rounding": rounding_label,
                "margin_floor": float(margin_floor),
                "responsible": responsible.strip(),
                "reason": reason.strip(),
            }

        preview_data = st.session_state.get("price_adjustment_preview")
        if isinstance(preview_data, dict):
            rows = [dict(row) for row in preview_data.get("rows", [])]
            total_change = sum(_num(row.get("difference")) for row in rows)
            blocked = [row for row in rows if row.get("blocked")]
            st.markdown("#### Vista previa")
            preview_metrics = st.columns(4)
            preview_metrics[0].metric("Precios a modificar", str(len(rows)))
            preview_metrics[1].metric("Protegidos por piso", str(len(blocked)))
            preview_metrics[2].metric("Variación acumulada", format_money(total_change, get_currency()))
            preview_metrics[3].metric("Margen promedio", f"{sum(_num(row.get('effective_margin')) for row in rows) / max(len(rows), 1):,.1f}%")

            st.download_button(
                "Descargar vista previa CSV",
                data=_export(rows),
                file_name=f"vista_previa_ajuste_precios_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

            for row in rows[:100]:
                with st.container(border=True):
                    cols = st.columns([3, 1, 1, 1, 1])
                    cols[0].markdown(f"**{row.get('name', 'Producto')}**")
                    cols[0].caption(f"{row.get('source')} · {row.get('category')} · {row.get('source_id')}")
                    cols[1].metric("Actual", format_money(_num(row.get("current_price")), str(row.get("currency", get_currency()))))
                    cols[2].metric("Final", format_money(_num(row.get("adjusted_price")), str(row.get("currency", get_currency()))))
                    cols[3].metric("Diferencia", format_money(_num(row.get("difference")), str(row.get("currency", get_currency()))))
                    cols[4].metric("Margen", f"{_num(row.get('effective_margin')):,.1f}%")
                    if row.get("blocked"):
                        st.warning("La propuesta fue elevada al piso protegido para evitar pérdida o margen insuficiente.")

            if st.button("Aplicar lote de ajustes", type="primary", use_container_width=True):
                if not str(preview_data.get("responsible", "")).strip() or not str(preview_data.get("reason", "")).strip():
                    st.error("Responsable y motivo son obligatorios para aplicar el lote.")
                elif not rows:
                    st.error("La vista previa no contiene precios.")
                else:
                    batch_id = f"PADJ-{uuid4().hex[:8].upper()}"
                    _apply(rows, str(preview_data.get("responsible", "")), str(preview_data.get("reason", "")), batch_id)
                    batches.append({
                        "batch_id": batch_id,
                        "method": preview_data.get("method", ""),
                        "value": preview_data.get("value", 0),
                        "rounding": preview_data.get("rounding", ""),
                        "margin_floor": preview_data.get("margin_floor", 0),
                        "responsible": preview_data.get("responsible", ""),
                        "reason": preview_data.get("reason", ""),
                        "affected_count": len(rows),
                        "total_change": total_change,
                        "created_at_utc": _now(),
                    })
                    _save("price_adjustment_batches", batches)
                    st.session_state.pop("price_adjustment_preview", None)
                    st.success("Lote aplicado correctamente.")
                    st.rerun()

    with floors_tab:
        with st.form("price_floor_rule_form", clear_on_submit=True):
            columns = st.columns(4)
            scope = columns[0].selectbox("Alcance", ("General", "Categoría", "Producto"))
            if scope == "Categoría":
                value = columns[1].selectbox("Valor", categories if categories else ("Sin categoría",))
            elif scope == "Producto":
                options = {f"{row.get('name')} · {row.get('source_id')}": str(row.get("source_id", "")) for row in active_rows}
                selected = columns[1].selectbox("Valor", tuple(options.keys()))
                value = options[selected]
            else:
                columns[1].text_input("Valor", value="Todos", disabled=True)
                value = "Todos"
            minimum_price = columns[2].number_input("Precio mínimo", min_value=0.0, value=0.0, step=0.1)
            responsible = columns[3].text_input("Responsable")
            note = st.text_input("Motivo o referencia")
            submitted = st.form_submit_button("Guardar regla", type="primary", use_container_width=True)
        if submitted:
            if minimum_price <= 0 or not responsible.strip():
                st.error("Precio mínimo y responsable son obligatorios.")
            else:
                floors.append({
                    "rule_id": f"PFL-{uuid4().hex[:8].upper()}",
                    "scope": scope,
                    "value": value,
                    "minimum_price": float(minimum_price),
                    "responsible": responsible.strip(),
                    "note": note.strip(),
                    "active": True,
                    "created_at_utc": _now(),
                })
                _save("price_floor_rules", floors)
                st.rerun()

        for rule in floors:
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{rule.get('scope', '')} · {rule.get('value', '')}**")
                cols[0].caption(f"{rule.get('responsible', '')} · {rule.get('note', '')}")
                cols[1].metric("Piso", format_money(_num(rule.get("minimum_price")), get_currency()))
                if cols[2].button("Desactivar", key=f"disable_floor_{rule.get('rule_id')}", use_container_width=True, disabled=not rule.get("active", True)):
                    changed = []
                    for current in floors:
                        row = dict(current)
                        if row.get("rule_id") == rule.get("rule_id"):
                            row["active"] = False
                            row["disabled_at_utc"] = _now()
                        changed.append(row)
                    _save("price_floor_rules", changed)
                    st.rerun()

    with consistency_tab:
        st.markdown("#### Validaciones de rentabilidad")
        if not below_cost and not low_margin:
            st.success("No se detectan precios por debajo del costo ni con margen crítico.")
        for row in below_cost:
            st.error(f"{row.get('name')}: precio {format_money(_num(row.get('current_price')), str(row.get('currency', get_currency())))} por debajo del costo {format_money(_num(row.get('unit_cost')), str(row.get('currency', get_currency())))}.")
        for row in low_margin:
            if row not in below_cost:
                st.warning(f"{row.get('name')}: margen actual {_margin(_num(row.get('current_price')), _num(row.get('unit_cost'))):,.1f}%.")

        st.markdown("#### Regla B/N vs color")
        bw_rows = [row for row in active_rows if any(token in str(row.get("name", "")).casefold() for token in ("blanco y negro", "b/n", "bn"))]
        color_rows = [row for row in active_rows if "color" in str(row.get("name", "")).casefold()]
        violations = []
        for color in color_rows:
            comparable = [bw for bw in bw_rows if str(bw.get("category", "")) == str(color.get("category", ""))]
            if comparable:
                highest_bw = max(_num(row.get("current_price")) for row in comparable)
                if _num(color.get("current_price")) < highest_bw:
                    violations.append((color, highest_bw))
        if not violations:
            st.success("No se detectan precios a color inferiores a comparables en blanco y negro.")
        for color, bw_price in violations:
            st.error(f"{color.get('name')}: el precio a color está por debajo del comparable B/N de {format_money(bw_price, str(color.get('currency', get_currency())))}.")

    with history_tab:
        if not history:
            st.info("No hay ajustes aplicados.")
        for row in reversed(history[-200:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row.get('name', 'Producto')} · {row.get('batch_id', '')}**")
                cols[0].caption(f"{row.get('responsible', '')} · {row.get('reason', '')}")
                cols[1].metric("Anterior", format_money(_num(row.get("previous_price")), get_currency()))
                cols[2].metric("Nuevo", format_money(_num(row.get("new_price")), get_currency()))
                cols[3].metric("Margen", f"{_num(row.get('effective_margin')):,.1f}%")

    render_info_card(
        "Precio protegido",
        "Los ajustes masivos respetan costo, margen mínimo, pisos comerciales y trazabilidad por lote.",
        "CONTROL COMERCIAL",
    )


app_shell.FUNCTIONAL_MODULES["Ajustar precios"] = render_price_adjustment_plus
