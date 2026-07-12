"""Capa enterprise para movimientos de inventario."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.inventory_movements_plus import render_inventory_movements_plus
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save, item_name as _item_name


def _activate_backup() -> None:
    for section, label in (
        ("inventory_movement_requests", "Solicitudes de movimientos de inventario"),
        ("inventory_transfer_orders", "Transferencias internas de inventario"),
        ("inventory_movement_rules", "Reglas de control de movimientos"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


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


def _available(item: dict) -> float:
    return _num(item.get("available_quantity", item.get("quantity")))


def _append_applied_movement(item: dict, movement_type: str, movement_class: str, quantity: float, reason: str, responsible: str, reference: str, location: str) -> None:
    movements = _rows("inventory_movements")
    previous = _available(item)
    resulting = previous + quantity if movement_type == "Entrada" else max(previous - quantity, 0.0)
    movements.append({
        "movement_id": uuid4().hex[:10],
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
        "location": location.strip(),
        "status": "Aplicado",
        "reversed": False,
        "previous_quantity": previous,
        "resulting_quantity": resulting,
    })
    _save("inventory_movements", movements)
    items = _rows("inventory_registry")
    changed = []
    for row in items:
        current = dict(row)
        if str(current.get("item_id", "")) == str(item.get("item_id", "")):
            current["available_quantity"] = resulting
            current["updated_at_utc"] = _now()
        changed.append(current)
    _save("inventory_registry", changed)


def _export_requests(requests: list[dict], items: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Solicitud", "Material", "Tipo", "Clase", "Cantidad", "Valor", "Estado", "Solicitado por", "Aprobado por", "Motivo"])
    for request in requests:
        item_id = str(request.get("item_id", ""))
        writer.writerow([
            request.get("request_id", ""),
            _item_name(item_id, items),
            request.get("movement_type", ""),
            request.get("movement_class", ""),
            request.get("quantity", 0),
            _num(request.get("quantity")) * _unit_cost(item_id, items),
            request.get("status", ""),
            request.get("requested_by", ""),
            request.get("approved_by", ""),
            request.get("reason", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def _risk_alerts(movements: list[dict], items: list[dict]) -> list[str]:
    alerts: list[str] = []
    now = datetime.now()
    recent = [row for row in movements if (created := _dt(row.get("created_at_utc"))) and created >= now - timedelta(days=30)]
    by_material = Counter(str(row.get("item_name", "Material")) for row in recent if row.get("movement_class") in {"Ajuste", "Merma", "Reverso"})
    by_owner = Counter(str(row.get("responsible", "Sin asignar")) for row in recent if row.get("movement_class") in {"Ajuste", "Merma", "Reverso"})
    for material, count in by_material.items():
        if count >= 3:
            alerts.append(f"{material} tiene {count} ajustes/mermas/reversos en 30 días. Revisar conteo físico o proceso de consumo.")
    for owner, count in by_owner.items():
        if owner != "Sin asignar" and count >= 5:
            alerts.append(f"{owner} concentra {count} movimientos sensibles en 30 días. Revisar autorización y capacitación.")
    for row in recent:
        value = _movement_value(row, items)
        if row.get("movement_class") in {"Merma", "Ajuste"} and value >= 20:
            alerts.append(f"Movimiento sensible de alto valor: {row.get('movement_id')} por {format_money(value)}.")
    return alerts


def render_inventory_movements_enterprise() -> None:
    render_page_header(
        "Movimientos de inventario · control enterprise",
        "Agrega aprobaciones, transferencias, reglas de riesgo y reportes ejecutivos sobre el historial.",
    )

    render_inventory_movements_plus()

    items = _rows("inventory_registry")
    movements = _rows("inventory_movements")
    requests = _rows("inventory_movement_requests")
    transfers = _rows("inventory_transfer_orders")
    rules = _rows("inventory_movement_rules")
    active_requests = [row for row in requests if row.get("status") == "Pendiente"]
    sensitive = [row for row in movements if row.get("movement_class") in {"Ajuste", "Merma", "Reverso"}]
    alerts = _risk_alerts(movements, items)

    st.divider()
    st.markdown("### Gobierno de movimientos")
    metrics = st.columns(5)
    metrics[0].metric("Solicitudes pendientes", str(len(active_requests)))
    metrics[1].metric("Transferencias", str(len(transfers)))
    metrics[2].metric("Movimientos sensibles", str(len(sensitive)))
    metrics[3].metric("Alertas", str(len(alerts)))
    metrics[4].metric("Reglas", str(len(rules)))

    request_tab, approval_tab, transfer_tab, exceptions_tab, rules_tab = st.tabs(("Solicitudes", "Aprobación", "Transferencias", "Excepciones", "Reglas"))

    item_options = {f"{item.get('name', 'Material')} · {item.get('item_id', '')}": str(item.get("item_id", "")) for item in items}

    with request_tab:
        st.caption("Usa solicitudes para movimientos delicados antes de tocar la existencia real.")
        if not item_options:
            st.info("No hay materiales registrados.")
        else:
            with st.form("inventory_movement_request_form", clear_on_submit=True):
                selected = st.selectbox("Material", tuple(item_options.keys()))
                item_id = item_options[selected]
                item = next(row for row in items if str(row.get("item_id", "")) == item_id)
                cols = st.columns(4)
                movement_type = cols[0].selectbox("Tipo", ("Entrada", "Salida"))
                movement_class = cols[1].selectbox("Clase", ("Ajuste", "Merma", "Transferencia", "Uso interno", "Devolución", "Otro"))
                quantity = cols[2].number_input("Cantidad", min_value=0.01, value=1.0, step=1.0)
                requested_by = cols[3].text_input("Solicitado por")
                reference = st.text_input("Referencia")
                reason = st.text_area("Justificación", max_chars=600)
                submitted = st.form_submit_button("Crear solicitud", type="primary", use_container_width=True)
            if submitted:
                if not requested_by.strip() or not reason.strip():
                    st.error("Solicitante y justificación son obligatorios.")
                elif movement_type == "Salida" and quantity > _available(item):
                    st.error("La salida solicitada supera la existencia disponible.")
                else:
                    requests.append({
                        "request_id": f"MVR-{uuid4().hex[:8].upper()}",
                        "item_id": item_id,
                        "movement_type": movement_type,
                        "movement_class": movement_class,
                        "quantity": float(quantity),
                        "reference": reference.strip(),
                        "reason": reason.strip(),
                        "requested_by": requested_by.strip(),
                        "status": "Pendiente",
                        "created_at_utc": _now(),
                    })
                    _save("inventory_movement_requests", requests)
                    st.rerun()
        st.download_button(
            "Descargar solicitudes CSV",
            data=_export_requests(requests, items),
            file_name=f"solicitudes_movimientos_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not requests,
        )

    with approval_tab:
        if not active_requests:
            st.info("No hay solicitudes pendientes.")
        for request in reversed(active_requests):
            item = next((row for row in items if str(row.get("item_id", "")) == str(request.get("item_id", ""))), {})
            value = _num(request.get("quantity")) * _unit_cost(str(request.get("item_id", "")), items)
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{request.get('request_id', '')} · {_item_name(str(request.get('item_id', '')), items)}**")
                cols[0].caption(f"{request.get('movement_type')} · {request.get('movement_class')} · {request.get('requested_by')}")
                cols[1].metric("Cantidad", f"{_num(request.get('quantity')):,.2f}")
                cols[2].metric("Valor", format_money(value))
                st.write(str(request.get("reason", "")))
                with st.form(f"approve_request_{request.get('request_id')}"):
                    decision = st.selectbox("Decisión", ("Aprobar y aplicar", "Rechazar"), key=f"decision_{request.get('request_id')}")
                    approved_by = st.text_input("Responsable de aprobación", key=f"approver_{request.get('request_id')}")
                    note = st.text_area("Nota", max_chars=400, key=f"note_{request.get('request_id')}")
                    submitted = st.form_submit_button("Guardar decisión", type="primary", use_container_width=True)
                if submitted:
                    if not approved_by.strip():
                        st.error("Indica responsable de aprobación.")
                    else:
                        changed = []
                        for row in requests:
                            current = dict(row)
                            if current.get("request_id") == request.get("request_id"):
                                current["status"] = "Aprobada" if decision == "Aprobar y aplicar" else "Rechazada"
                                current["approved_by"] = approved_by.strip() if decision == "Aprobar y aplicar" else ""
                                current["rejected_by"] = approved_by.strip() if decision == "Rechazar" else ""
                                current["approval_note"] = note.strip()
                                current["approval_at_utc"] = _now()
                            changed.append(current)
                        _save("inventory_movement_requests", changed)
                        if decision == "Aprobar y aplicar":
                            _append_applied_movement(
                                item,
                                str(request.get("movement_type", "")),
                                str(request.get("movement_class", "")),
                                _num(request.get("quantity")),
                                f"Solicitud {request.get('request_id')}: {request.get('reason', '')}",
                                approved_by,
                                str(request.get("reference", "")),
                                str(item.get("location", "")),
                            )
                        st.rerun()

    with transfer_tab:
        if not item_options:
            st.info("No hay materiales para transferir.")
        else:
            with st.form("inventory_transfer_form", clear_on_submit=True):
                selected = st.selectbox("Material", tuple(item_options.keys()), key="transfer_item")
                item_id = item_options[selected]
                item = next(row for row in items if str(row.get("item_id", "")) == item_id)
                cols = st.columns(4)
                quantity = cols[0].number_input("Cantidad", min_value=0.01, value=1.0, step=1.0)
                source = cols[1].text_input("Ubicación origen", value=str(item.get("location", "")))
                target = cols[2].text_input("Ubicación destino")
                responsible = cols[3].text_input("Responsable")
                reason = st.text_area("Motivo", max_chars=400)
                submitted = st.form_submit_button("Registrar transferencia", type="primary", use_container_width=True)
            if submitted:
                if not target.strip() or not responsible.strip() or not reason.strip():
                    st.error("Destino, responsable y motivo son obligatorios.")
                elif quantity > _available(item):
                    st.error("La transferencia supera la existencia disponible.")
                else:
                    transfer_id = f"TRF-{uuid4().hex[:8].upper()}"
                    transfers.append({
                        "transfer_id": transfer_id,
                        "item_id": item_id,
                        "quantity": float(quantity),
                        "source_location": source.strip(),
                        "target_location": target.strip(),
                        "responsible": responsible.strip(),
                        "reason": reason.strip(),
                        "status": "Registrada",
                        "created_at_utc": _now(),
                    })
                    _save("inventory_transfer_orders", transfers)
                    _append_applied_movement(item, "Salida", "Transferencia", float(quantity), f"Salida por transferencia {transfer_id}: {reason}", responsible, transfer_id, source)
                    refreshed = next((row for row in _rows("inventory_registry") if str(row.get("item_id", "")) == item_id), item)
                    _append_applied_movement(refreshed, "Entrada", "Transferencia", float(quantity), f"Entrada por transferencia {transfer_id}: {reason}", responsible, transfer_id, target)
                    st.rerun()
        for transfer in reversed(transfers[-50:]):
            with st.container(border=True):
                st.markdown(f"**{transfer.get('transfer_id', '')} · {_item_name(str(transfer.get('item_id', '')), items)}**")
                st.caption(f"{transfer.get('source_location', '')} → {transfer.get('target_location', '')} · {transfer.get('responsible', '')}")
                st.metric("Cantidad", f"{_num(transfer.get('quantity')):,.2f}")

    with exceptions_tab:
        if not alerts:
            st.success("No hay alertas de riesgo en movimientos recientes.")
        for alert in alerts:
            st.warning(alert)
        st.markdown("#### Resumen sensible")
        by_class: dict[str, float] = defaultdict(float)
        for movement in sensitive:
            by_class[str(movement.get("movement_class", "Operación"))] += _movement_value(movement, items)
        for name, value in sorted(by_class.items(), key=lambda row: row[1], reverse=True):
            st.write(f"**{name}:** {format_money(value)}")

    with rules_tab:
        st.caption("Estas reglas sirven como referencia gerencial para revisar movimientos delicados.")
        with st.form("movement_rules_form"):
            columns = st.columns(4)
            approval_amount = columns[0].number_input("Aprobación desde monto", min_value=0.0, value=_num(rules[0].get("approval_amount"), 20.0) if rules else 20.0, step=1.0)
            max_merma = columns[1].number_input("Merma máxima sin revisión", min_value=0.0, value=_num(rules[0].get("max_merma"), 5.0) if rules else 5.0, step=1.0)
            max_adjustments = columns[2].number_input("Ajustes mensuales permitidos", min_value=0, value=int(_num(rules[0].get("max_adjustments"), 3)) if rules else 3, step=1)
            reviewer = columns[3].text_input("Revisor sugerido", value=str(rules[0].get("reviewer", "")) if rules else "")
            submitted = st.form_submit_button("Guardar reglas", type="primary", use_container_width=True)
        if submitted:
            _save("inventory_movement_rules", [{
                "approval_amount": float(approval_amount),
                "max_merma": float(max_merma),
                "max_adjustments": int(max_adjustments),
                "reviewer": reviewer.strip(),
                "updated_at_utc": _now(),
            }])
            st.rerun()

    render_info_card(
        "Movimiento gobernado",
        "Los movimientos sensibles ahora pueden solicitarse, aprobarse, transferirse y revisarse con reglas de riesgo.",
        "CONTROL ENTERPRISE",
    )


app_shell.FUNCTIONAL_MODULES["Movimientos de inventario"] = render_inventory_movements_enterprise
