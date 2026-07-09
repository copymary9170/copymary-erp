"""Reversos de pagos con aprobación, riesgo, evidencia y auditoría."""

from datetime import date, datetime, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, payment_reversals as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("payment_reversal_requests", "Solicitudes de reverso de pagos"),
        ("payment_reversal_audit", "Auditoría de reversos de pagos"),
        ("payment_reversal_evidence", "Evidencias de reversos de pagos"),
        ("payment_reversal_reviews", "Revisiones de reversos de pagos"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


PAYMENT_SOURCES = (
    ("Cliente", "payment_records", "sale_id", "sales_registry", "sale_id", "Egreso", "Reverso de cobro"),
    ("Proveedor", "supplier_payment_records", "purchase_id", "purchases_registry", "purchase_id", "Ingreso", "Reverso de pago a proveedor"),
    ("Equipo", "team_payments", "member_id", "team_members", "member_id", "Ingreso", "Reverso de pago al personal"),
)


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


def _is_reversed(payment: dict) -> bool:
    return bool(payment.get("reversed"))


def _name_for(kind: str, payment: dict) -> str:
    if kind == "Equipo":
        member_id = str(payment.get("member_id", ""))
        for member in _rows("team_members"):
            if str(member.get("member_id", "")) == member_id:
                return str(member.get("name", "Colaborador"))
        return "Colaborador"
    if kind == "Cliente":
        sale_id = str(payment.get("sale_id", ""))
        for sale in _rows("sales_registry"):
            if str(sale.get("sale_id", "")) == sale_id:
                return str(sale.get("customer_name", sale.get("description", "Cliente")))
        return "Cliente"
    purchase_id = str(payment.get("purchase_id", ""))
    for purchase in _rows("purchases_registry"):
        if str(purchase.get("purchase_id", "")) == purchase_id:
            return str(purchase.get("supplier", purchase.get("supplier_name", "Proveedor")))
    return "Proveedor"


def _all_active_payments() -> list[dict]:
    output: list[dict] = []
    for kind, payment_key, link_key, _registry_key, _registry_link, cash_type, cash_category in PAYMENT_SOURCES:
        for payment in _rows(payment_key):
            if _is_reversed(payment):
                continue
            current = dict(payment)
            current["_kind"] = kind
            current["_payment_key"] = payment_key
            current["_link_key"] = link_key
            current["_cash_type"] = cash_type
            current["_cash_category"] = cash_category
            current["_display_name"] = _name_for(kind, payment)
            output.append(current)
    return sorted(output, key=lambda row: str(row.get("payment_date", row.get("created_at_utc", ""))), reverse=True)


def _risk(payment: dict) -> tuple[str, list[str]]:
    warnings: list[str] = []
    amount = abs(_num(payment.get("amount")))
    payment_date = str(payment.get("payment_date", payment.get("created_at_utc", "")))[:10]
    try:
        age = (date.today() - date.fromisoformat(payment_date)).days
    except ValueError:
        age = 0
    if amount >= 50:
        warnings.append("Monto alto para reverso.")
    if age >= 7:
        warnings.append("Pago con más de 7 días registrado.")
    if not str(payment.get("reference", "")).strip():
        warnings.append("Pago sin referencia.")
    if payment.get("_kind") == "Cliente":
        warnings.append("Puede cambiar el estado de cobro de la venta.")
    if len(warnings) >= 2 or amount >= 100:
        return "Alto", warnings
    if warnings:
        return "Medio", warnings
    return "Bajo", warnings


def _audit(action: str, kind: str, payment_id: str, responsible: str, note: str) -> None:
    audit = _rows("payment_reversal_audit")
    audit.append({
        "audit_id": f"PRA-{uuid4().hex[:8].upper()}",
        "action": action,
        "kind": kind,
        "payment_id": payment_id,
        "responsible": responsible.strip() or "Sin asignar",
        "note": note.strip(),
        "created_at_utc": _now(),
    })
    _save("payment_reversal_audit", audit)


def _active_paid(records: list[dict], link_key: str, link_id: str) -> float:
    return sum(_num(item.get("amount")) for item in records if str(item.get(link_key, "")) == link_id and not item.get("reversed"))


def _status(total: float, paid: float) -> str:
    if paid <= 0:
        return "Pendiente"
    if paid + 0.0001 >= total:
        return "Pagado"
    return "Abono"


def _mark_reversed(records: list[dict], payment_id: str, reason: str, responsible: str, request_id: str = "") -> list[dict]:
    updated: list[dict] = []
    for record in records:
        current = dict(record)
        if str(record.get("payment_id", "")) == payment_id:
            current["reversed"] = True
            current["reversed_at_utc"] = _now()
            current["reversal_reason"] = reason
            current["reversed_by"] = responsible.strip()
            current["reversal_request_id"] = request_id
        updated.append(current)
    return updated


def _reverse_cash(cash: list[dict], payment: dict, responsible: str, reason: str) -> list[dict]:
    payment_id = str(payment.get("payment_id", ""))
    reference = f"REV-{payment_id}"
    if any(str(item.get("reference", "")) == reference for item in cash):
        return cash
    cash.append({
        "movement_id": uuid4().hex[:10],
        "created_at_utc": _now(),
        "movement_type": str(payment.get("_cash_type", "Ingreso")),
        "category": str(payment.get("_cash_category", "Reverso de pago")),
        "amount": _num(payment.get("amount")),
        "payment_method": str(payment.get("payment_method", "Otro")),
        "reference": reference,
        "notes": reason or f"Reverso de pago {payment_id}",
        "responsible": responsible.strip() or "Sin asignar",
        "status": "Aplicado",
        "source_reversal": True,
    })
    return cash


def _apply_reversal(payment: dict, responsible: str, reason: str, request_id: str = "") -> None:
    kind = str(payment.get("_kind", ""))
    payment_id = str(payment.get("payment_id", ""))
    payment_key = str(payment.get("_payment_key", ""))
    link_key = str(payment.get("_link_key", ""))
    payments = _mark_reversed(_rows(payment_key), payment_id, reason, responsible, request_id)
    cash = _reverse_cash(_rows("cash_movements"), payment, responsible, reason)
    _save(payment_key, payments)
    _save("cash_movements", cash)

    if kind == "Cliente":
        sale_id = str(payment.get("sale_id", ""))
        sales = []
        for sale in _rows("sales_registry"):
            current = dict(sale)
            if str(current.get("sale_id", "")) == sale_id:
                paid = _active_paid(payments, link_key, sale_id)
                current["payment_status"] = _status(_num(current.get("total")), paid)
                current["cash_registered"] = current["payment_status"] == "Pagado"
            sales.append(current)
        _save("sales_registry", sales)
    elif kind == "Proveedor":
        purchase_id = str(payment.get("purchase_id", ""))
        purchases = []
        for purchase in _rows("purchases_registry"):
            current = dict(purchase)
            if str(current.get("purchase_id", "")) == purchase_id:
                paid = _active_paid(payments, link_key, purchase_id)
                current["payment_status"] = _status(_num(current.get("total")), paid)
                current["cash_registered"] = current["payment_status"] == "Pagado"
            purchases.append(current)
        _save("purchases_registry", purchases)
    _audit("Reverso aplicado", kind, payment_id, responsible, reason)


def _export(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Tipo", "Pago", "Monto", "Estado", "Riesgo", "Solicitado", "Aprobado", "Motivo", "Fecha"])
    for row in rows:
        writer.writerow([row.get("request_id", ""), row.get("kind", ""), row.get("payment_id", ""), row.get("amount", 0), row.get("status", ""), row.get("risk", ""), row.get("requested_by", ""), row.get("approved_by", ""), row.get("reason", ""), row.get("created_at_utc", "")])
    return buffer.getvalue().encode("utf-8-sig")


def render_payment_reversals_plus() -> None:
    render_page_header("Reversos de pagos", "Controla solicitudes, aprobaciones, riesgo, evidencia y auditoría de reversos.")

    requests = _rows("payment_reversal_requests")
    evidence = _rows("payment_reversal_evidence")
    audit = _rows("payment_reversal_audit")
    reviews = _rows("payment_reversal_reviews")
    active_payments = _all_active_payments()
    pending = [row for row in requests if row.get("status") == "Pendiente"]
    approved = [row for row in requests if row.get("status") == "Aprobada"]
    reversed_total = sum(1 for key in ("payment_records", "supplier_payment_records", "team_payments") for row in _rows(key) if row.get("reversed"))

    metrics = st.columns(5)
    metrics[0].metric("Pagos reversables", str(len(active_payments)))
    metrics[1].metric("Pendientes", str(len(pending)))
    metrics[2].metric("Aprobadas", str(len(approved)))
    metrics[3].metric("Reversos", str(reversed_total))
    metrics[4].metric("Evidencias", str(len(evidence)))

    request_tab, approval_tab, direct_tab, evidence_tab, audit_tab = st.tabs(("Solicitudes", "Aprobación", "Reverso directo", "Evidencias", "Auditoría"))

    with request_tab:
        if not active_payments:
            st.info("No hay pagos activos para solicitar reverso.")
        else:
            options = {f"{row.get('_kind')} · {row.get('_display_name')} · {format_money(_num(row.get('amount')), get_currency())} · {row.get('payment_id')}": row for row in active_payments[:300]}
            with st.form("payment_reversal_request_form", clear_on_submit=True):
                selected = st.selectbox("Pago", tuple(options.keys()))
                requested_by = st.text_input("Solicitado por")
                reason = st.text_area("Motivo", max_chars=700)
                expected_effect = st.text_area("Efecto esperado", max_chars=500)
                submitted = st.form_submit_button("Crear solicitud", type="primary", use_container_width=True)
            if submitted:
                if not requested_by.strip() or not reason.strip():
                    st.error("Solicitante y motivo son obligatorios.")
                else:
                    payment = options[selected]
                    risk, warnings = _risk(payment)
                    requests.append({
                        "request_id": f"PRR-{uuid4().hex[:8].upper()}",
                        "kind": payment.get("_kind", ""),
                        "payment_id": str(payment.get("payment_id", "")),
                        "amount": _num(payment.get("amount")),
                        "risk": risk,
                        "warnings": warnings,
                        "requested_by": requested_by.strip(),
                        "reason": reason.strip(),
                        "expected_effect": expected_effect.strip(),
                        "status": "Pendiente",
                        "created_at_utc": _now(),
                    })
                    _save("payment_reversal_requests", requests)
                    _audit("Solicitud creada", str(payment.get("_kind", "")), str(payment.get("payment_id", "")), requested_by, reason)
                    st.rerun()
        st.download_button("Descargar solicitudes CSV", data=_export(requests), file_name="solicitudes_reversos_pagos.csv", mime="text/csv", use_container_width=True, disabled=not requests)

    with approval_tab:
        if not pending:
            st.info("No hay solicitudes pendientes.")
        for request in reversed(pending):
            with st.container(border=True):
                st.markdown(f"**{request.get('request_id')} · {request.get('kind')} · pago {request.get('payment_id')}**")
                st.caption(f"Riesgo {request.get('risk')} · {format_money(_num(request.get('amount')), get_currency())}")
                for warning in request.get("warnings", [])[:5]:
                    st.warning(str(warning))
                st.write(request.get("reason", ""))
                with st.form(f"approve_payment_reversal_{request.get('request_id')}"):
                    decision = st.selectbox("Decisión", ("Aprobar", "Rechazar"), key=f"decision_{request.get('request_id')}")
                    responsible = st.text_input("Responsable", key=f"responsible_{request.get('request_id')}")
                    note = st.text_area("Nota", max_chars=500, key=f"note_{request.get('request_id')}")
                    submitted = st.form_submit_button("Guardar decisión", type="primary", use_container_width=True)
                if submitted:
                    if not responsible.strip():
                        st.error("Indica responsable.")
                    else:
                        changed = []
                        for row in requests:
                            current = dict(row)
                            if current.get("request_id") == request.get("request_id"):
                                current["status"] = "Aprobada" if decision == "Aprobar" else "Rechazada"
                                current["approved_by"] = responsible.strip() if decision == "Aprobar" else ""
                                current["decision_by"] = responsible.strip()
                                current["decision_note"] = note.strip()
                                current["decision_at_utc"] = _now()
                            changed.append(current)
                        _save("payment_reversal_requests", changed)
                        _audit(f"Solicitud {decision.lower()}", str(request.get("kind", "")), str(request.get("payment_id", "")), responsible, note)
                        st.rerun()

        st.markdown("#### Aplicar solicitudes aprobadas")
        by_id = {str(row.get("payment_id", "")): row for row in active_payments}
        for request in reversed(approved):
            payment = by_id.get(str(request.get("payment_id", "")))
            with st.container(border=True):
                st.markdown(f"**{request.get('request_id')} · pago {request.get('payment_id')}**")
                if payment is None:
                    st.warning("El pago ya no está activo o ya fue revertido.")
                    continue
                with st.form(f"apply_payment_reversal_{request.get('request_id')}"):
                    responsible = st.text_input("Responsable de aplicación", key=f"apply_by_{request.get('request_id')}")
                    confirmation = st.text_input("Escribe REVERSAR", key=f"confirm_{request.get('request_id')}")
                    submitted = st.form_submit_button("Aplicar reverso", type="primary", use_container_width=True)
                if submitted:
                    if confirmation.strip().upper() != "REVERSAR" or not responsible.strip():
                        st.error("Responsable y confirmación REVERSAR son obligatorios.")
                    else:
                        _apply_reversal(payment, responsible, str(request.get("reason", "")), str(request.get("request_id", "")))
                        changed = []
                        for row in requests:
                            current = dict(row)
                            if current.get("request_id") == request.get("request_id"):
                                current["status"] = "Aplicada"
                                current["applied_by"] = responsible.strip()
                                current["applied_at_utc"] = _now()
                            changed.append(current)
                        _save("payment_reversal_requests", changed)
                        st.rerun()

    with direct_tab:
        st.warning("Usa reverso directo solo para correcciones simples. Para montos altos usa solicitud y aprobación.")
        if not active_payments:
            st.info("No hay pagos activos para revertir.")
        else:
            options = {f"{row.get('_kind')} · {row.get('_display_name')} · {format_money(_num(row.get('amount')), get_currency())} · {row.get('payment_id')}": row for row in active_payments[:300]}
            with st.form("direct_payment_reversal_form", clear_on_submit=True):
                selected = st.selectbox("Pago", tuple(options.keys()), key="direct_reversal_payment")
                responsible = st.text_input("Responsable")
                reason = st.text_area("Motivo", max_chars=700)
                confirmation = st.text_input("Escribe REVERSAR para confirmar")
                submitted = st.form_submit_button("Aplicar reverso directo", type="primary", use_container_width=True)
            if submitted:
                payment = options[selected]
                risk, warnings = _risk(payment)
                if risk == "Alto":
                    st.error("Este pago es de riesgo alto. Crea solicitud y aprobación antes de aplicar el reverso.")
                elif confirmation.strip().upper() != "REVERSAR" or not responsible.strip() or not reason.strip():
                    st.error("Responsable, motivo y confirmación REVERSAR son obligatorios.")
                else:
                    _apply_reversal(payment, responsible, reason, "DIRECTO")
                    st.rerun()

    with evidence_tab:
        reversed_payments = []
        for key, kind in (("payment_records", "Cliente"), ("supplier_payment_records", "Proveedor"), ("team_payments", "Equipo")):
            for payment in _rows(key):
                if payment.get("reversed"):
                    reversed_payments.append({"kind": kind, **payment})
        if not reversed_payments:
            st.info("No hay reversos para documentar.")
        else:
            options = {f"{row.get('kind')} · {row.get('payment_id')} · {format_money(_num(row.get('amount')), get_currency())}": row for row in reversed_payments[:300]}
            with st.form("payment_reversal_evidence_form", clear_on_submit=True):
                selected = st.selectbox("Reverso", tuple(options.keys()))
                evidence_type = st.selectbox("Tipo", ("Referencia bancaria", "Captura", "Nota interna", "Autorización", "Otro"))
                reference = st.text_input("Referencia")
                responsible = st.text_input("Responsable")
                note = st.text_area("Detalle", max_chars=600)
                submitted = st.form_submit_button("Guardar evidencia", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not note.strip():
                    st.error("Responsable y detalle son obligatorios.")
                else:
                    row = options[selected]
                    evidence.append({
                        "evidence_id": f"PRE-{uuid4().hex[:8].upper()}",
                        "kind": row.get("kind", ""),
                        "payment_id": row.get("payment_id", ""),
                        "evidence_type": evidence_type,
                        "reference": reference.strip(),
                        "responsible": responsible.strip(),
                        "note": note.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("payment_reversal_evidence", evidence)
                    st.rerun()
        for item in reversed(evidence[-100:]):
            st.write(f"**{item.get('evidence_id')} · {item.get('kind')} · {item.get('payment_id')}** — {item.get('responsible')}: {item.get('note')}")

    with audit_tab:
        with st.form("payment_reversal_review_form", clear_on_submit=True):
            reviewer = st.text_input("Revisado por")
            conclusion = st.text_area("Conclusión", max_chars=700)
            submitted = st.form_submit_button("Guardar revisión", type="primary", use_container_width=True)
        if submitted:
            if not reviewer.strip() or not conclusion.strip():
                st.error("Revisor y conclusión son obligatorios.")
            else:
                reviews.append({"review_id": f"PRV-{uuid4().hex[:8].upper()}", "reviewer": reviewer.strip(), "conclusion": conclusion.strip(), "created_at_utc": _now()})
                _save("payment_reversal_reviews", reviews)
                st.rerun()
        st.markdown("#### Auditoría")
        if not audit:
            st.info("No hay auditoría de reversos.")
        for item in reversed(audit[-150:]):
            st.write(f"**{item.get('action')}** · {item.get('kind')} · {item.get('payment_id')} · {item.get('responsible')} · {item.get('created_at_utc')} — {item.get('note')}")
        st.markdown("#### Revisiones")
        for item in reversed(reviews[-50:]):
            st.write(f"**{item.get('review_id')}** · {item.get('reviewer')}: {item.get('conclusion')}")

    render_info_card("Reverso controlado", "Cada reverso puede pasar por solicitud, aprobación, evidencia y auditoría sin borrar el pago original.", "CONTROL DE PAGOS")


app_shell.FUNCTIONAL_MODULES["Reversos de pagos"] = render_payment_reversals_plus
