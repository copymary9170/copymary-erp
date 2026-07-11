"""Inventario avanzado con auditoría, reservas, lotes y conteos."""

from collections import Counter, defaultdict
from datetime import date, timedelta
from uuid import uuid4
import csv
import io

import streamlit as st

from src import inventory as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("inventory_reservations", "Reservas de inventario"),
        ("inventory_counts", "Conteos físicos"),
        ("inventory_lots", "Lotes de inventario"),
        ("inventory_audit_log", "Auditoría de inventario"),
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


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _item_name(item_id: str, items: list[dict]) -> str:
    for item in items:
        if str(item.get("item_id", "")) == item_id:
            return str(item.get("name", "Material"))
    return "Material no disponible"


def _unit_cost(item: dict) -> float:
    return _num(item.get("purchase_cost")) / max(_num(item.get("purchased_quantity"), 1.0), 0.01)


def _available(item: dict) -> float:
    return _num(item.get("available_quantity", item.get("quantity")))


def _reserved_for(item_id: str, reservations: list[dict]) -> float:
    return sum(
        _num(item.get("quantity"))
        for item in reservations
        if str(item.get("item_id", "")) == item_id and str(item.get("status", "Activa")) == "Activa"
    )


def _audit(action: str, item_id: str, note: str, responsible: str = "") -> None:
    log = _rows("inventory_audit_log")
    log.append({
        "audit_id": uuid4().hex[:12],
        "action": action,
        "item_id": item_id,
        "note": note.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("inventory_audit_log", log)


def _update_item(item_id: str, updates: dict) -> None:
    items = _rows("inventory_registry")
    changed = []
    for item in items:
        row = dict(item)
        if str(row.get("item_id", "")) == item_id:
            row.update(updates)
            row["updated_at_utc"] = _now()
        changed.append(row)
    _save("inventory_registry", changed)


def _movement(item: dict, movement_type: str, quantity: float, reason: str, responsible: str = "") -> None:
    movements = _rows("inventory_movements")
    previous = _available(item)
    resulting = previous + quantity if movement_type == "Entrada" else max(previous - quantity, 0.0)
    movements.append({
        "movement_id": uuid4().hex[:10],
        "created_at_utc": _now(),
        "item_id": str(item.get("item_id", "")),
        "item_name": str(item.get("name", "Material")),
        "movement_type": movement_type,
        "quantity": float(quantity),
        "unit_name": str(item.get("unit_name", "unidad")),
        "reason": reason.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "previous_quantity": previous,
        "resulting_quantity": resulting,
    })
    _save("inventory_movements", movements)
    _update_item(str(item.get("item_id", "")), {"available_quantity": resulting})
    _audit(movement_type, str(item.get("item_id", "")), reason, responsible)


def _export(items: list[dict], reservations: list[dict], lots: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ID", "Nombre", "Categoría", "Ubicación", "Unidad", "Disponible", "Reservado",
        "Libre", "Mínimo", "Punto de reposición", "Costo unitario", "Valor", "Lotes", "Estado",
    ])
    for item in items:
        item_id = str(item.get("item_id", ""))
        available = _available(item)
        reserved = _reserved_for(item_id, reservations)
        free = max(available - reserved, 0.0)
        minimum = _num(item.get("minimum_stock"))
        reorder = _num(item.get("reorder_point", minimum))
        item_lots = [lot for lot in lots if str(lot.get("item_id", "")) == item_id]
        state = "Crítico" if free <= minimum else "Reposición" if free <= reorder else "Disponible"
        writer.writerow([
            item_id,
            item.get("name", ""),
            item.get("category", ""),
            item.get("location", ""),
            item.get("unit_name", "unidad"),
            available,
            reserved,
            free,
            minimum,
            reorder,
            _unit_cost(item),
            available * _unit_cost(item),
            len(item_lots),
            state,
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_inventory_plus() -> None:
    render_page_header(
        "Inventario",
        "Controla existencias reales, reservas, lotes, conteos físicos y trazabilidad de materiales.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_inventory()
    finally:
        base.render_page_header = original_header

    items = _rows("inventory_registry")
    reservations = _rows("inventory_reservations")
    counts = _rows("inventory_counts")
    lots = _rows("inventory_lots")
    audit = _rows("inventory_audit_log")
    movements = _rows("inventory_movements")
    today = date.today()

    total_value = sum(_available(item) * _unit_cost(item) for item in items)
    total_reserved = sum(_reserved_for(str(item.get("item_id", "")), reservations) for item in items)
    low_items = [item for item in items if max(_available(item) - _reserved_for(str(item.get("item_id", "")), reservations), 0) <= _num(item.get("minimum_stock"))]
    expiring_lots = [
        lot for lot in lots
        if _as_date(lot.get("expiry_date")) and today <= _as_date(lot.get("expiry_date")) <= today + timedelta(days=30)
    ]
    expired_lots = [lot for lot in lots if _as_date(lot.get("expiry_date")) and _as_date(lot.get("expiry_date")) < today]

    st.divider()
    st.markdown("### Control avanzado")
    metrics = st.columns(5)
    metrics[0].metric("Valor disponible", format_money(total_value))
    metrics[1].metric("Reservado", f"{total_reserved:,.2f}")
    metrics[2].metric("Stock bajo real", str(len(low_items)))
    metrics[3].metric("Lotes vencidos", str(len(expired_lots)))
    metrics[4].metric("Auditorías", str(len(audit)))

    if low_items:
        st.warning(f"Hay {len(low_items)} material(es) con existencia libre en mínimo o por debajo.")
    if expired_lots:
        st.error(f"Hay {len(expired_lots)} lote(s) vencido(s).")

    dashboard_tab, reservation_tab, count_tab, lot_tab, edit_tab, audit_tab = st.tabs(
        ("Panel", "Reservas", "Conteo físico", "Lotes", "Editar", "Auditoría")
    )

    item_options = {
        f"{item.get('name', 'Material')} · {item.get('item_id', '')}": str(item.get("item_id", ""))
        for item in items
    }

    with dashboard_tab:
        filters = st.columns(4)
        query = filters[0].text_input("Buscar material", placeholder="Nombre, categoría, ubicación o ID").strip().casefold()
        category_filter = filters[1].selectbox("Categoría", ("Todas", *sorted({str(item.get("category", "Otro")) for item in items})))
        state_filter = filters[2].selectbox("Estado", ("Todos", "Disponible", "Reposición", "Crítico", "Reservado"))
        sort_by = filters[3].selectbox("Ordenar", ("Valor", "Nombre", "Existencia libre", "Categoría"))

        visible = []
        for item in items:
            item_id = str(item.get("item_id", ""))
            reserved = _reserved_for(item_id, reservations)
            available = _available(item)
            free = max(available - reserved, 0.0)
            minimum = _num(item.get("minimum_stock"))
            reorder = _num(item.get("reorder_point", minimum))
            state = "Crítico" if free <= minimum else "Reposición" if free <= reorder else "Disponible"
            text = " ".join(str(item.get(field, "")) for field in ("name", "category", "location", "item_id")).casefold()
            if query and query not in text:
                continue
            if category_filter != "Todas" and str(item.get("category", "Otro")) != category_filter:
                continue
            if state_filter == "Reservado" and reserved <= 0:
                continue
            if state_filter not in {"Todos", "Reservado"} and state != state_filter:
                continue
            visible.append((item, state, free, reserved, available * _unit_cost(item)))

        key_functions = {
            "Valor": lambda row: row[4],
            "Nombre": lambda row: str(row[0].get("name", "")),
            "Existencia libre": lambda row: row[2],
            "Categoría": lambda row: str(row[0].get("category", "")),
        }
        for item, state, free, reserved, value in sorted(visible, key=key_functions[sort_by], reverse=sort_by == "Valor"):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1, 1])
                cols[0].markdown(f"**{item.get('name', 'Material')}**")
                cols[0].caption(f"{item.get('category', 'Otro')} · {item.get('location') or 'Sin ubicación'} · ID {item.get('item_id', '')}")
                cols[1].metric("Disponible", f"{_available(item):,.2f}")
                cols[2].metric("Reservado", f"{reserved:,.2f}")
                cols[3].metric("Libre", f"{free:,.2f}")
                cols[4].metric("Estado", state)
                st.progress(min(max(free / max(_num(item.get("reorder_point", item.get("minimum_stock", 1))), 0.01), 0), 1.0))

        if items:
            st.download_button(
                "Descargar inventario avanzado CSV",
                data=_export(items, reservations, lots),
                file_name=f"inventario_avanzado_{today.isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with reservation_tab:
        if not item_options:
            st.info("No hay materiales para reservar.")
        else:
            with st.form("inventory_reservation_form", clear_on_submit=True):
                selected = st.selectbox("Material", tuple(item_options.keys()))
                item_id = item_options[selected]
                item = next(row for row in items if str(row.get("item_id", "")) == item_id)
                free = max(_available(item) - _reserved_for(item_id, reservations), 0.0)
                columns = st.columns(4)
                quantity = columns[0].number_input("Cantidad", min_value=0.0, max_value=float(free), value=0.0, step=1.0)
                source = columns[1].selectbox("Origen", ("Pedido", "Producción", "Cotización", "Uso interno", "Otro"))
                reference = columns[2].text_input("Referencia")
                due_date = columns[3].date_input("Vence", value=today + timedelta(days=7))
                responsible = st.text_input("Responsable")
                note = st.text_area("Nota", max_chars=400)
                submitted = st.form_submit_button("Reservar inventario", type="primary", use_container_width=True)
            if submitted:
                if quantity <= 0:
                    st.error("La cantidad a reservar debe ser mayor que cero.")
                else:
                    reservations.append({
                        "reservation_id": f"RSV-{uuid4().hex[:8].upper()}",
                        "item_id": item_id,
                        "quantity": float(quantity),
                        "source": source,
                        "reference": reference.strip(),
                        "due_date": due_date.isoformat(),
                        "responsible": responsible.strip() or "Sin asignar",
                        "note": note.strip(),
                        "status": "Activa",
                        "created_at_utc": _now(),
                    })
                    _save("inventory_reservations", reservations)
                    _audit("Reserva", item_id, f"Reserva {quantity:,.2f} para {source} {reference}", responsible)
                    st.rerun()

        active_reservations = [row for row in reservations if row.get("status") == "Activa"]
        if not active_reservations:
            st.info("No hay reservas activas.")
        for reservation in reversed(active_reservations[-50:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{_item_name(str(reservation.get('item_id', '')), items)}**")
                cols[0].caption(f"{reservation.get('source', '')} · {reservation.get('reference', '')} · vence {reservation.get('due_date', '')}")
                cols[1].metric("Cantidad", f"{_num(reservation.get('quantity')):,.2f}")
                if cols[2].button("Liberar", key=f"release_reservation_{reservation.get('reservation_id')}", use_container_width=True):
                    updated = []
                    for row in reservations:
                        current = dict(row)
                        if current.get("reservation_id") == reservation.get("reservation_id"):
                            current["status"] = "Liberada"
                            current["released_at_utc"] = _now()
                        updated.append(current)
                    _save("inventory_reservations", updated)
                    _audit("Liberación", str(reservation.get("item_id", "")), "Reserva liberada", str(reservation.get("responsible", "")))
                    st.rerun()

    with count_tab:
        if not item_options:
            st.info("No hay materiales para contar.")
        else:
            with st.form("physical_count_form", clear_on_submit=True):
                selected = st.selectbox("Material", tuple(item_options.keys()), key="count_item")
                item_id = item_options[selected]
                item = next(row for row in items if str(row.get("item_id", "")) == item_id)
                system_quantity = _available(item)
                columns = st.columns(3)
                counted = columns[0].number_input("Cantidad física", min_value=0.0, value=float(system_quantity), step=1.0)
                responsible = columns[1].text_input("Responsable del conteo")
                adjust = columns[2].checkbox("Ajustar existencia al guardar", value=False)
                note = st.text_area("Observación", max_chars=500)
                submitted = st.form_submit_button("Guardar conteo", type="primary", use_container_width=True)
            if submitted:
                variance = float(counted) - system_quantity
                counts.append({
                    "count_id": f"CNT-{uuid4().hex[:8].upper()}",
                    "item_id": item_id,
                    "system_quantity": system_quantity,
                    "counted_quantity": float(counted),
                    "variance": variance,
                    "responsible": responsible.strip() or "Sin asignar",
                    "note": note.strip(),
                    "adjusted": bool(adjust),
                    "created_at_utc": _now(),
                })
                _save("inventory_counts", counts)
                _audit("Conteo físico", item_id, f"Diferencia {variance:,.2f}. {note}", responsible)
                if adjust and abs(variance) > 0:
                    movement_type = "Entrada" if variance > 0 else "Salida"
                    _movement(item, movement_type, abs(variance), "Ajuste por conteo físico", responsible)
                st.rerun()

        for count in reversed(counts[-50:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{_item_name(str(count.get('item_id', '')), items)}**")
                cols[0].caption(f"{count.get('created_at_utc', '')} · {count.get('responsible', '')}")
                cols[1].metric("Sistema", f"{_num(count.get('system_quantity')):,.2f}")
                cols[2].metric("Físico", f"{_num(count.get('counted_quantity')):,.2f}")
                cols[3].metric("Diferencia", f"{_num(count.get('variance')):+,.2f}")

    with lot_tab:
        if not item_options:
            st.info("No hay materiales para crear lotes.")
        else:
            with st.form("inventory_lot_form", clear_on_submit=True):
                selected = st.selectbox("Material", tuple(item_options.keys()), key="lot_item")
                item_id = item_options[selected]
                columns = st.columns(4)
                lot_code = columns[0].text_input("Código de lote", value=f"LOT-{today.strftime('%Y%m%d')}-{uuid4().hex[:4].upper()}")
                quantity = columns[1].number_input("Cantidad del lote", min_value=0.0, value=0.0, step=1.0)
                expiry_date = columns[2].date_input("Vencimiento", value=None)
                location = columns[3].text_input("Ubicación")
                supplier = st.text_input("Proveedor o referencia")
                submitted = st.form_submit_button("Registrar lote", type="primary", use_container_width=True)
            if submitted:
                if not lot_code.strip() or quantity <= 0:
                    st.error("Indica código de lote y cantidad mayor que cero.")
                elif any(str(lot.get("lot_code", "")).strip().casefold() == lot_code.strip().casefold() for lot in lots):
                    st.error("Ya existe un lote con ese código.")
                else:
                    lots.append({
                        "lot_id": uuid4().hex[:12],
                        "lot_code": lot_code.strip(),
                        "item_id": item_id,
                        "quantity": float(quantity),
                        "expiry_date": expiry_date.isoformat() if expiry_date else "",
                        "location": location.strip(),
                        "supplier": supplier.strip(),
                        "status": "Disponible",
                        "created_at_utc": _now(),
                    })
                    _save("inventory_lots", lots)
                    _audit("Lote", item_id, f"Lote {lot_code} registrado", supplier)
                    st.rerun()

        for lot in reversed(lots[-80:]):
            expiry = _as_date(lot.get("expiry_date"))
            state = "Vencido" if expiry and expiry < today else "Próximo" if expiry and expiry <= today + timedelta(days=30) else "Vigente"
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{lot.get('lot_code', 'Lote')} · {_item_name(str(lot.get('item_id', '')), items)}**")
                cols[0].caption(f"{lot.get('supplier') or 'Sin proveedor'} · {lot.get('location') or 'Sin ubicación'}")
                cols[1].metric("Cantidad", f"{_num(lot.get('quantity')):,.2f}")
                cols[2].metric("Vence", str(lot.get("expiry_date") or "Sin fecha"))
                cols[3].metric("Estado", state)

    with edit_tab:
        if not item_options:
            st.info("No hay materiales para editar.")
        else:
            selected = st.selectbox("Material", tuple(item_options.keys()), key="edit_item")
            item_id = item_options[selected]
            item = next(row for row in items if str(row.get("item_id", "")) == item_id)
            with st.form("inventory_edit_form"):
                first = st.columns(4)
                name = first[0].text_input("Nombre", value=str(item.get("name", "")))
                category = first[1].text_input("Categoría", value=str(item.get("category", "Otro")))
                location = first[2].text_input("Ubicación", value=str(item.get("location", "")))
                unit_name = first[3].text_input("Unidad", value=str(item.get("unit_name", "unidad")))
                second = st.columns(4)
                purchase_cost = second[0].number_input("Costo total", min_value=0.0, value=_num(item.get("purchase_cost")), step=1.0)
                purchased_quantity = second[1].number_input("Cantidad base", min_value=0.01, value=_num(item.get("purchased_quantity"), 1.0), step=1.0)
                minimum_stock = second[2].number_input("Mínimo", min_value=0.0, value=_num(item.get("minimum_stock")), step=1.0)
                reorder_point = second[3].number_input("Punto reposición", min_value=0.0, value=_num(item.get("reorder_point", item.get("minimum_stock"))), step=1.0)
                responsible = st.text_input("Responsable")
                submitted = st.form_submit_button("Guardar ficha", type="primary", use_container_width=True)
            if submitted:
                if not name.strip() or not unit_name.strip():
                    st.error("Nombre y unidad son obligatorios.")
                elif purchase_cost <= 0:
                    st.error("El costo total debe ser mayor que cero.")
                else:
                    _update_item(item_id, {
                        "name": name.strip(),
                        "category": category.strip() or "Otro",
                        "location": location.strip(),
                        "unit_name": unit_name.strip(),
                        "purchase_cost": float(purchase_cost),
                        "purchased_quantity": float(purchased_quantity),
                        "minimum_stock": float(minimum_stock),
                        "reorder_point": float(reorder_point),
                    })
                    _audit("Edición", item_id, "Ficha de inventario actualizada", responsible)
                    st.rerun()

    with audit_tab:
        visible = audit[-100:]
        if not visible:
            st.info("No hay auditoría avanzada de inventario.")
        for entry in reversed(visible):
            with st.container(border=True):
                st.markdown(f"**{entry.get('action', 'Acción')} · {_item_name(str(entry.get('item_id', '')), items)}**")
                st.write(str(entry.get("note", "")))
                st.caption(f"{entry.get('created_at_utc', '')} · {entry.get('responsible', 'Sin asignar')}")

    render_info_card(
        "Inventario confiable",
        "Las reservas, conteos, lotes y auditorías se guardan en el respaldo general.",
        "CONTROL DE EXISTENCIAS",
    )
