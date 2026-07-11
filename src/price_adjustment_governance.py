"""Aprobaciones, vigencias, promociones y reversión de precios."""

from datetime import date, timedelta
from uuid import uuid4
import streamlit as st

from src import app_shell, price_adjustment_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("price_change_requests", "Solicitudes de cambio de precios"),
        ("price_promotions", "Promociones de precios"),
        ("price_rollbacks", "Reversiones de precios"),
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


def _sources() -> list[dict]:
    return base._source_rows()


def _find(source: str, source_id: str, rows: list[dict]) -> dict:
    return next((row for row in rows if str(row.get("source")) == source and str(row.get("source_id")) == source_id), {})


def _apply_price(source: str, source_id: str, new_price: float, responsible: str, reference: str) -> float:
    old_price = 0.0
    if source == "Costeo":
        rows = _rows("saved_prices")
        changed = []
        for item in rows:
            row = dict(item)
            if str(row.get("price_id", "")) == source_id:
                old_price = _num(row.get("unit_price"))
                row["previous_unit_price"] = old_price
                row["unit_price"] = float(new_price)
                row["price_reference"] = reference
                row["price_updated_at_utc"] = _now()
                row["price_updated_by"] = responsible.strip() or "Sin asignar"
            changed.append(row)
        _save("saved_prices", changed)
    else:
        rows = _rows("products_registry")
        changed = []
        for item in rows:
            row = dict(item)
            if str(row.get("product_id", "")) == source_id:
                old_price = _num(row.get("sale_price"))
                row["previous_sale_price"] = old_price
                row["sale_price"] = float(new_price)
                row["price_reference"] = reference
                row["price_updated_at_utc"] = _now()
                row["price_updated_by"] = responsible.strip() or "Sin asignar"
            changed.append(row)
        _save("products_registry", changed)
    return old_price


def render_price_adjustment_governance() -> None:
    render_page_header("Ajustar precios", "Aprueba, programa, promociona y revierte cambios de precios.")
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_price_adjustment_plus()
    finally:
        base.render_page_header = original_header

    sources = _sources()
    requests = _rows("price_change_requests")
    promotions = _rows("price_promotions")
    rollbacks = _rows("price_rollbacks")
    batches = _rows("price_adjustment_batches")
    history = _rows("price_adjustment_history")
    today = date.today()

    pending = [row for row in requests if row.get("status") == "Pendiente"]
    scheduled = [row for row in requests if row.get("status") == "Aprobada" and str(row.get("effective_date", "")) > today.isoformat()]
    active_promotions = [row for row in promotions if row.get("status") == "Activa" and str(row.get("end_date", "")) >= today.isoformat()]

    st.divider()
    st.markdown("### Gobierno comercial")
    metrics = st.columns(4)
    metrics[0].metric("Solicitudes pendientes", str(len(pending)))
    metrics[1].metric("Cambios programados", str(len(scheduled)))
    metrics[2].metric("Promociones activas", str(len(active_promotions)))
    metrics[3].metric("Reversiones", str(len(rollbacks)))

    request_tab, approval_tab, promotion_tab, rollback_tab = st.tabs(("Solicitudes", "Aprobación", "Promociones", "Reversión"))
    options = {f"{row.get('name', 'Producto')} · {row.get('source')} · {row.get('source_id')}": row for row in sources}

    with request_tab:
        if not options:
            st.info("No hay precios disponibles.")
        else:
            with st.form("price_change_request_form", clear_on_submit=True):
                selected = st.selectbox("Producto o servicio", tuple(options.keys()))
                source_row = options[selected]
                cols = st.columns(4)
                proposed = cols[0].number_input("Precio propuesto", min_value=0.0, value=_num(source_row.get("current_price")), step=0.1)
                effective_date = cols[1].date_input("Vigencia", value=today)
                requested_by = cols[2].text_input("Solicitado por")
                priority = cols[3].selectbox("Prioridad", ("Normal", "Alta", "Urgente"))
                reason = st.text_area("Justificación", max_chars=500)
                submitted = st.form_submit_button("Crear solicitud", type="primary", use_container_width=True)
            if submitted:
                cost = _num(source_row.get("unit_cost"))
                if not requested_by.strip() or not reason.strip():
                    st.error("Solicitante y justificación son obligatorios.")
                elif proposed <= 0 or (cost > 0 and proposed < cost):
                    st.error("El precio debe ser positivo y no puede quedar por debajo del costo.")
                else:
                    requests.append({
                        "request_id": f"PCR-{uuid4().hex[:8].upper()}",
                        "source": str(source_row.get("source", "")),
                        "source_id": str(source_row.get("source_id", "")),
                        "current_price": _num(source_row.get("current_price")),
                        "proposed_price": float(proposed),
                        "effective_date": effective_date.isoformat(),
                        "requested_by": requested_by.strip(),
                        "priority": priority,
                        "reason": reason.strip(),
                        "status": "Pendiente",
                        "created_at_utc": _now(),
                    })
                    _save("price_change_requests", requests)
                    st.rerun()

    with approval_tab:
        if not pending:
            st.info("No hay solicitudes pendientes.")
        for request in reversed(pending):
            source = str(request.get("source", ""))
            source_id = str(request.get("source_id", ""))
            source_row = _find(source, source_id, sources)
            current = _num(source_row.get("current_price"))
            proposed = _num(request.get("proposed_price"))
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{source_row.get('name', 'Producto')} · {request.get('request_id', '')}**")
                cols[0].caption(f"{request.get('priority')} · vigencia {request.get('effective_date')} · {request.get('requested_by')}")
                cols[1].metric("Actual", format_money(current, get_currency()))
                cols[2].metric("Propuesto", format_money(proposed, get_currency()))
                with st.form(f"approve_price_{request.get('request_id')}"):
                    decision = st.selectbox("Decisión", ("Aprobar", "Rechazar"), key=f"decision_{request.get('request_id')}")
                    responsible = st.text_input("Responsable", key=f"responsible_{request.get('request_id')}")
                    note = st.text_area("Nota", max_chars=300, key=f"note_{request.get('request_id')}")
                    submitted = st.form_submit_button("Guardar decisión", type="primary", use_container_width=True)
                if submitted:
                    if not responsible.strip():
                        st.error("Indica responsable.")
                    else:
                        changed = []
                        for item in requests:
                            row = dict(item)
                            if row.get("request_id") == request.get("request_id"):
                                row["status"] = "Aprobada" if decision == "Aprobar" else "Rechazada"
                                row["approved_by"] = responsible.strip() if decision == "Aprobar" else ""
                                row["decision_note"] = note.strip()
                                row["decision_at_utc"] = _now()
                            changed.append(row)
                        _save("price_change_requests", changed)
                        if decision == "Aprobar" and str(request.get("effective_date", "")) <= today.isoformat():
                            old_price = _apply_price(source, source_id, proposed, responsible, str(request.get("request_id", "")))
                            for row in changed:
                                if row.get("request_id") == request.get("request_id"):
                                    row["status"] = "Aplicada"
                                    row["previous_price"] = old_price
                                    row["applied_at_utc"] = _now()
                            _save("price_change_requests", changed)
                        st.rerun()

        due = [row for row in requests if row.get("status") == "Aprobada" and str(row.get("effective_date", "")) <= today.isoformat()]
        for request in due:
            label = _find(str(request.get("source", "")), str(request.get("source_id", "")), sources).get("name", "Producto")
            if st.button(f"Aplicar {request.get('request_id')} · {label}", key=f"apply_{request.get('request_id')}", use_container_width=True):
                old_price = _apply_price(str(request.get("source", "")), str(request.get("source_id", "")), _num(request.get("proposed_price")), str(request.get("approved_by", "")), str(request.get("request_id", "")))
                changed = []
                for item in requests:
                    row = dict(item)
                    if row.get("request_id") == request.get("request_id"):
                        row["status"] = "Aplicada"
                        row["previous_price"] = old_price
                        row["applied_at_utc"] = _now()
                    changed.append(row)
                _save("price_change_requests", changed)
                st.rerun()

    with promotion_tab:
        if not options:
            st.info("No hay precios disponibles.")
        else:
            with st.form("price_promotion_form", clear_on_submit=True):
                selected = st.selectbox("Producto", tuple(options.keys()), key="promotion_product")
                source_row = options[selected]
                cols = st.columns(4)
                discount = cols[0].number_input("Descuento %", min_value=0.0, max_value=95.0, value=10.0, step=1.0)
                start_date = cols[1].date_input("Inicio", value=today)
                end_date = cols[2].date_input("Fin", value=today + timedelta(days=7))
                responsible = cols[3].text_input("Responsable")
                reason = st.text_input("Nombre de la promoción")
                submitted = st.form_submit_button("Crear promoción", type="primary", use_container_width=True)
            if submitted:
                current = _num(source_row.get("current_price"))
                promo_price = current * (1 - float(discount) / 100.0)
                floor = max(_num(source_row.get("unit_cost")), base._floor_for(source_row, _rows("price_floor_rules")))
                if not responsible.strip() or not reason.strip():
                    st.error("Responsable y nombre son obligatorios.")
                elif end_date < start_date or promo_price < floor:
                    st.error("La promoción tiene fechas inválidas o baja del piso protegido.")
                else:
                    promotions.append({
                        "promotion_id": f"PROM-{uuid4().hex[:8].upper()}",
                        "source": str(source_row.get("source", "")),
                        "source_id": str(source_row.get("source_id", "")),
                        "regular_price": current,
                        "promotional_price": promo_price,
                        "discount_percent": float(discount),
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "responsible": responsible.strip(),
                        "reason": reason.strip(),
                        "status": "Activa" if start_date <= today <= end_date else "Programada",
                        "created_at_utc": _now(),
                    })
                    _save("price_promotions", promotions)
                    st.rerun()
        for promotion in reversed(promotions[-100:]):
            source_row = _find(str(promotion.get("source", "")), str(promotion.get("source_id", "")), sources)
            st.write(f"**{source_row.get('name', 'Producto')} · {promotion.get('reason', '')}** — {format_money(_num(promotion.get('promotional_price')), get_currency())} · {promotion.get('start_date')} a {promotion.get('end_date')}")

    with rollback_tab:
        if not batches:
            st.info("No hay lotes aplicados.")
        else:
            options_batches = {f"{row.get('batch_id')} · {row.get('affected_count', 0)} precio(s)": str(row.get("batch_id", "")) for row in reversed(batches)}
            selected = st.selectbox("Lote", tuple(options_batches.keys()))
            batch_id = options_batches[selected]
            batch_history = [row for row in history if str(row.get("batch_id", "")) == batch_id]
            with st.form("price_rollback_form"):
                responsible = st.text_input("Responsable de reversión")
                reason = st.text_area("Motivo", max_chars=400)
                confirmed = st.checkbox("Confirmo la restauración de los precios anteriores")
                submitted = st.form_submit_button("Reversar lote", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not reason.strip() or not confirmed:
                    st.error("Responsable, motivo y confirmación son obligatorios.")
                elif any(str(row.get("batch_id", "")) == batch_id for row in rollbacks):
                    st.error("Este lote ya fue reversado.")
                elif not batch_history:
                    st.error("No hay historial para ese lote.")
                else:
                    count = 0
                    for row in batch_history:
                        _apply_price(str(row.get("source", "")), str(row.get("source_id", "")), _num(row.get("previous_price")), responsible, f"REV-{batch_id}")
                        count += 1
                    rollbacks.append({
                        "rollback_id": f"RBK-{uuid4().hex[:8].upper()}",
                        "batch_id": batch_id,
                        "affected_count": count,
                        "responsible": responsible.strip(),
                        "reason": reason.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("price_rollbacks", rollbacks)
                    st.success(f"Se restauraron {count} precio(s).")
                    st.rerun()

    render_info_card(
        "Cambios reversibles",
        "Los precios pueden aprobarse, programarse, promocionarse y revertirse sin perder trazabilidad.",
        "GOBIERNO COMERCIAL",
    )


app_shell.FUNCTIONAL_MODULES["Ajustar precios"] = render_price_adjustment_governance
