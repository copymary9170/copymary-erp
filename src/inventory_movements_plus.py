"""Movimientos de inventario con controles, reversos y análisis."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import inventory_movements as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money


def _activate_backup() -> None:
    for section, label in (
        ("inventory_movement_reversals", "Reversos de movimientos de inventario"),
        ("inventory_movement_approvals", "Aprobaciones de movimientos de inventario"),
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


def _dt(value) -> datetime | None:
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


def _unit_cost(item_id: str, items: list[dict]) -> float:
    item = next((row for row in items if str(row.get("item_id", "")) == item_id), {})
    return _num(item.get("purchase_cost")) / max(_num(item.get("purchased_quantity"), 1.0), 0.01)


def _movement_value(movement: dict, items: list[dict]) -> float:
    return _num(movement.get("quantity")) * _unit_cost(str(movement.get("item_id", "")), items)


def _enrich_legacy(movements: list[dict]) -> list[dict]:
    changed = []
    for movement in movements:
        row = dict(movement)
        row.setdefault("movement_class", "Operación")
        row.setdefault("responsible", "Sin asignar")
        row.setdefault("reference", "")
        row.setdefault("location", "")
        row.setdefault("batch_code", "")
        row.setdefault("status", "Aplicado")
        row.setdefault("reversed", False)
        changed.append(row)
    return changed


def _update_item(item_id: str, new_quantity: float) -> None:
    items = _rows("inventory_registry")
    changed = []
    for item in items:
        row = dict(item)
        if str(row.get("item_id", "")) == item_id:
            row["available_quantity"] = max(float(new_quantity), 0.0)
            row["updated_at_utc"] = _now()
        changed.append(row)
    _save("inventory_registry", changed)


def _append_movement(item: dict, movement_type: str, quantity: float, reason: str, movement_class: str, responsible: str, reference: str, location: str, batch_code: str) -> None:
    movements = _enrich_legacy(_rows("inventory_movements"))
    previous = _num(item.get("available_quantity"))
    resulting = previous + quantity if movement_type == "Entrada" else previous - quantity
    movement_id = uuid4().hex[:10]
    movements.append({
        "movement_id": movement_id,
        "created_at_utc": _now(),
        "item_id": str(item.get("item_id", "")),
        "item_name": str(item.get("name", "Material")),
        "movement_type": movement_type,
        "movement_class": movement_class,
        "quantity": float(quantity),
        "unit_name": str(item.get("unit_name", "unidad")),
        "reason": reason.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "reference": reference.strip(),
        "location": location.strip() or str(item.get("location", "")),
        "batch_code": batch_code.strip(),
        "status": "Aplicado",
        "reversed": False,
        "previous_quantity": previous,
        "resulting_quantity": resulting,
    })
    _save("inventory_movements", movements)
    _update_item(str(item.get("item_id", "")), resulting)


def _reverse_movement(movement: dict, items: list[dict], responsible: str, reason: str) -> None:
    movements = _enrich_legacy(_rows("inventory_movements"))
    item_id = str(movement.get("item_id", ""))
    item = next((row for row in items if str(row.get("item_id", "")) == item_id), {})
    current = _num(item.get("available_quantity"))
    original_type = str(movement.get("movement_type", ""))
    reverse_type = "Salida" if original_type == "Entrada" else "Entrada"
    quantity = _num(movement.get("quantity"))
    resulting = current - quantity if reverse_type == "Salida" else current + quantity
    reversal_id = f"REV-{uuid4().hex[:8].upper()}"
    changed = []
    for row in movements:
        current_row = dict(row)
        if str(current_row.get("movement_id", "")) == str(movement.get("movement_id", "")):
            current_row["reversed"] = True
            current_row["status"] = "Reversado"
            current_row["reversal_id"] = reversal_id
            current_row["reversed_at_utc"] = _now()
        changed.append(current_row)
    changed.append({
        "movement_id": reversal_id,
        "created_at_utc": _now(),
        "item_id": item_id,
        "item_name": str(movement.get("item_name", "Material")),
        "movement_type": reverse_type,
        "movement_class": "Reverso",
        "quantity": quantity,
        "unit_name": str(movement.get("unit_name", "unidad")),
        "reason": reason.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "reference": str(movement.get("movement_id", "")),
        "location": str(movement.get("location", "")),
        "batch_code": str(movement.get("batch_code", "")),
        "status": "Aplicado",
        "reversed": False,
        "previous_quantity": current,
        "resulting_quantity": resulting,
    })
    _save("inventory_movements", changed)
    _update_item(item_id, resulting)
    reversals = _rows("inventory_movement_reversals")
    reversals.append({
        "reversal_id": reversal_id,
        "source_movement_id": str(movement.get("movement_id", "")),
        "item_id": item_id,
        "quantity": quantity,
        "responsible": responsible.strip() or "Sin asignar",
        "reason": reason.strip(),
        "created_at_utc": _now(),
    })
    _save("inventory_movement_reversals", reversals)


def _export(rows: list[dict], items: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Fecha", "Material", "Tipo", "Clase", "Cantidad", "Costo", "Responsable", "Referencia", "Ubicación", "Lote", "Estado", "Motivo"])
    for row in rows:
        writer.writerow([
            row.get("movement_id", ""), row.get("created_at_utc", ""), row.get("item_name", ""),
            row.get("movement_type", ""), row.get("movement_class", ""), row.get("quantity", 0),
            _movement_value(row, items), row.get("responsible", ""), row.get("reference", ""),
            row.get("location", ""), row.get("batch_code", ""), row.get("status", ""), row.get("reason", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_inventory_movements_plus() -> None:
    render_page_header(
        "Movimientos de inventario",
        "Registra movimientos clasificados, conserva referencias y revierte errores sin borrar trazabilidad.",
    )

    items = _rows("inventory_registry")
    movements = _enrich_legacy(_rows("inventory_movements"))
    if movements != _rows("inventory_movements"):
        _save("inventory_movements", movements)

    active = [row for row in movements if not row.get("reversed")]
    entries = [row for row in active if row.get("movement_type") == "Entrada"]
    exits = [row for row in active if row.get("movement_type") == "Salida"]
    entry_value = sum(_movement_value(row, items) for row in entries)
    exit_value = sum(_movement_value(row, items) for row in exits)

    metrics = st.columns(5)
    metrics[0].metric("Movimientos", str(len(movements)))
    metrics[1].metric("Entradas", str(len(entries)))
    metrics[2].metric("Salidas", str(len(exits)))
    metrics[3].metric("Valor entradas", format_money(entry_value))
    metrics[4].metric("Valor salidas", format_money(exit_value))

    register_tab, history_tab, reverse_tab, analysis_tab, audit_tab = st.tabs(("Registrar", "Historial", "Reversar", "Análisis", "Auditoría"))

    with register_tab:
        if not items:
            st.info("No hay materiales registrados.")
        else:
            options = {f"{item.get('name', 'Material')} · {item.get('item_id', '')}": str(item.get("item_id", "")) for item in items}
            with st.form("advanced_inventory_movement_form", clear_on_submit=True):
                selected = st.selectbox("Material", tuple(options.keys()))
                item_id = options[selected]
                item = next(row for row in items if str(row.get("item_id", "")) == item_id)
                first = st.columns(4)
                movement_type = first[0].selectbox("Tipo", ("Entrada", "Salida"))
                movement_class = first[1].selectbox("Clase", ("Compra", "Producción", "Venta", "Ajuste", "Merma", "Transferencia", "Devolución", "Uso interno", "Otro"))
                quantity = first[2].number_input("Cantidad", min_value=0.01, value=1.0, step=1.0)
                responsible = first[3].text_input("Responsable")
                second = st.columns(3)
                reference = second[0].text_input("Referencia", placeholder="Pedido, compra, producción o factura")
                location = second[1].text_input("Ubicación", value=str(item.get("location", "")))
                batch_code = second[2].text_input("Lote")
                reason = st.text_area("Motivo", max_chars=500)
                confirmed = st.checkbox("Confirmo que la información es correcta")
                submitted = st.form_submit_button("Registrar movimiento", type="primary", use_container_width=True)
            if submitted:
                available = _num(item.get("available_quantity"))
                if not reason.strip() or not responsible.strip():
                    st.error("Motivo y responsable son obligatorios.")
                elif movement_type == "Salida" and float(quantity) > available:
                    st.error("La salida supera la existencia disponible.")
                elif not confirmed:
                    st.error("Confirma el movimiento antes de registrarlo.")
                else:
                    _append_movement(item, movement_type, float(quantity), reason, movement_class, responsible, reference, location, batch_code)
                    st.rerun()

    with history_tab:
        filters = st.columns(5)
        query = filters[0].text_input("Buscar", placeholder="Material, motivo, responsable, referencia").strip().casefold()
        type_filter = filters[1].selectbox("Tipo", ("Todos", "Entrada", "Salida"))
        class_filter = filters[2].selectbox("Clase", ("Todas", *sorted({str(row.get('movement_class', 'Operación')) for row in movements})))
        status_filter = filters[3].selectbox("Estado", ("Todos", "Aplicado", "Reversado"))
        period = filters[4].selectbox("Periodo", ("Todo", "7 días", "30 días", "90 días"))
        days = {"7 días": 7, "30 días": 30, "90 días": 90}.get(period)
        cutoff = datetime.now() - timedelta(days=days) if days else None
        visible = []
        for row in movements:
            text = " ".join(str(row.get(field, "")) for field in ("item_name", "reason", "responsible", "reference", "batch_code")).casefold()
            created = _dt(row.get("created_at_utc"))
            if query and query not in text:
                continue
            if type_filter != "Todos" and row.get("movement_type") != type_filter:
                continue
            if class_filter != "Todas" and row.get("movement_class") != class_filter:
                continue
            if status_filter != "Todos" and row.get("status", "Aplicado") != status_filter:
                continue
            if cutoff and (not created or created < cutoff):
                continue
            visible.append(row)
        st.caption(f"Mostrando {len(visible)} de {len(movements)} movimiento(s).")
        st.download_button("Descargar historial filtrado CSV", data=_export(visible, items), file_name=f"movimientos_inventario_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not visible)
        for row in reversed(visible[-150:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row.get('item_name', 'Material')} · {row.get('movement_id', '')}**")
                cols[0].caption(f"{row.get('movement_class', 'Operación')} · {row.get('responsible', 'Sin asignar')} · {row.get('reference') or 'Sin referencia'}")
                cols[1].metric("Tipo", str(row.get("movement_type", "")))
                cols[2].metric("Cantidad", f"{_num(row.get('quantity')):,.2f}")
                cols[3].metric("Estado", str(row.get("status", "Aplicado")))
                st.caption(f"{row.get('created_at_utc', '')} · {row.get('reason', '')}")

    with reverse_tab:
        reversible = [row for row in movements if not row.get("reversed") and row.get("movement_class") != "Reverso"]
        if not reversible:
            st.info("No hay movimientos disponibles para reversar.")
        else:
            options = {f"{row.get('movement_id', '')} · {row.get('item_name', '')} · {row.get('movement_type')} {row.get('quantity')}": str(row.get("movement_id", "")) for row in reversed(reversible)}
            selected = st.selectbox("Movimiento", tuple(options.keys()))
            movement = next(row for row in reversible if str(row.get("movement_id", "")) == options[selected])
            with st.form("inventory_movement_reversal_form"):
                responsible = st.text_input("Responsable del reverso")
                reason = st.text_area("Motivo del reverso", max_chars=500)
                confirmed = st.checkbox("Confirmo que deseo crear un movimiento compensatorio")
                submitted = st.form_submit_button("Reversar movimiento", type="primary", use_container_width=True)
            if submitted:
                item = next((row for row in items if str(row.get("item_id", "")) == str(movement.get("item_id", ""))), {})
                if not responsible.strip() or not reason.strip() or not confirmed:
                    st.error("Responsable, motivo y confirmación son obligatorios.")
                elif movement.get("movement_type") == "Entrada" and _num(item.get("available_quantity")) < _num(movement.get("quantity")):
                    st.error("No se puede reversar la entrada porque parte de esa existencia ya fue consumida.")
                else:
                    _reverse_movement(movement, items, responsible, reason)
                    st.rerun()

    with analysis_tab:
        by_class: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "quantity": 0.0, "value": 0.0})
        by_responsible = Counter()
        for row in active:
            name = str(row.get("movement_class", "Operación"))
            by_class[name]["count"] += 1
            by_class[name]["quantity"] += _num(row.get("quantity"))
            by_class[name]["value"] += _movement_value(row, items)
            by_responsible[str(row.get("responsible", "Sin asignar"))] += 1
        st.markdown("#### Por clase")
        for name, data in sorted(by_class.items(), key=lambda current: current[1]["value"], reverse=True):
            st.write(f"**{name}:** {int(data['count'])} movimiento(s) · {data['quantity']:,.2f} unidades · {format_money(data['value'])}")
        st.markdown("#### Responsables con más movimientos")
        for responsible, count in by_responsible.most_common(10):
            st.write(f"**{responsible}:** {count}")

    with audit_tab:
        issues = []
        for row in movements:
            previous = _num(row.get("previous_quantity"))
            quantity = _num(row.get("quantity"))
            expected = previous + quantity if row.get("movement_type") == "Entrada" else previous - quantity
            if abs(expected - _num(row.get("resulting_quantity"))) > 0.0001:
                issues.append((row, "La existencia resultante no coincide con el cálculo."))
            if not str(row.get("responsible", "")).strip() or row.get("responsible") == "Sin asignar":
                issues.append((row, "No tiene responsable identificado."))
            if not str(row.get("reason", "")).strip():
                issues.append((row, "No tiene motivo."))
        if not issues:
            st.success("No se detectan inconsistencias en el historial.")
        for row, issue in issues[:100]:
            st.warning(f"{row.get('movement_id', '')} · {row.get('item_name', '')}: {issue}")

    render_info_card(
        "Trazabilidad protegida",
        "Los errores se corrigen con movimientos compensatorios; el historial original no se elimina.",
        "CONTROL DE MOVIMIENTOS",
    )
