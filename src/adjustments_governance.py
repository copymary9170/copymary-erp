"""Anulaciones y ajustes con solicitud, riesgo, evidencia y conciliación."""

from collections import Counter
from datetime import date
from uuid import uuid4
import csv
import io

import streamlit as st

from src import adjustments as base, app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("adjustment_requests", "Solicitudes de anulaciones y ajustes"),
        ("adjustment_evidence", "Evidencias de anulaciones y ajustes"),
        ("adjustment_reviews", "Revisiones de anulaciones y ajustes"),
        ("adjustment_anomalies", "Anomalías de anulaciones y ajustes"),
        ("adjustment_period_locks", "Bloqueos de periodos de ajustes"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def _period(value: str = "") -> str:
    raw = str(value or date.today().isoformat())[:7]
    return raw if len(raw) == 7 else f"{date.today().year:04d}-{date.today().month:02d}"


def _available_operations() -> list[dict]:
    adjustments = _rows("adjustment_records")
    canceled_sales = {str(row.get("reference_id", "")) for row in adjustments if row.get("kind") == "Venta"}
    canceled_purchases = {str(row.get("reference_id", "")) for row in adjustments if row.get("kind") == "Compra"}
    operations: list[dict] = []
    for sale in _rows("sales_registry"):
        sale_id = str(sale.get("sale_id", ""))
        if sale_id and sale_id not in canceled_sales and sale.get("order_status") != "Cancelado":
            operations.append({
                "kind": "Venta",
                "reference_id": sale_id,
                "description": str(sale.get("description", "Venta")),
                "amount": _num(sale.get("total")),
                "date": str(sale.get("created_at_utc", ""))[:10],
                "payment_status": str(sale.get("payment_status", "")),
                "inventory_applied": bool(sale.get("inventory_applied", False)),
            })
    for purchase in _rows("purchases_registry"):
        purchase_id = str(purchase.get("purchase_id", ""))
        if purchase_id and purchase_id not in canceled_purchases and purchase.get("receipt_status") != "Cancelada":
            operations.append({
                "kind": "Compra",
                "reference_id": purchase_id,
                "description": str(purchase.get("material_name", "Compra")),
                "amount": _num(purchase.get("total")),
                "date": str(purchase.get("created_at_utc", ""))[:10],
                "payment_status": str(purchase.get("payment_status", "")),
                "inventory_applied": bool(purchase.get("inventory_applied", False)),
            })
    return sorted(operations, key=lambda row: str(row.get("date", "")), reverse=True)


def _risk(operation: dict) -> tuple[str, list[str]]:
    warnings = []
    amount = _num(operation.get("amount"))
    op_date = str(operation.get("date", ""))[:10]
    try:
        age = (date.today() - date.fromisoformat(op_date)).days
    except ValueError:
        age = 0
    if amount >= 100:
        warnings.append("Monto alto para anulación.")
    elif amount >= 50:
        warnings.append("Monto medio para anulación.")
    if age >= 7:
        warnings.append("Operación con más de 7 días.")
    if operation.get("payment_status") in {"Pagado", "Reembolsado"}:
        warnings.append("La operación tiene impacto en Caja.")
    if operation.get("inventory_applied"):
        warnings.append("La operación tiene impacto en Inventario.")
    if len(warnings) >= 2 or amount >= 100:
        return "Alto", warnings
    if warnings:
        return "Medio", warnings
    return "Bajo", warnings


def _adjustment_cash_rows() -> list[dict]:
    return [row for row in _rows("cash_movements") if str(row.get("reference", "")).startswith("REV-") or str(row.get("category", "")).casefold().startswith("reembolso")]


def _detect_anomalies() -> list[dict]:
    adjustments = _rows("adjustment_records")
    cash = _adjustment_cash_rows()
    cash_refs = Counter(str(row.get("reference", "")) for row in cash)
    anomalies = []
    for row in adjustments:
        adjustment_id = str(row.get("adjustment_id", ""))
        reference_id = str(row.get("reference_id", ""))
        expected_ref = f"REV-{reference_id}"
        amount = _num(row.get("amount"))
        if amount > 0 and cash_refs.get(expected_ref, 0) == 0:
            anomalies.append({"anomaly_id": f"ADA-{uuid4().hex[:8].upper()}", "adjustment_id": adjustment_id, "kind": row.get("kind", ""), "reference_id": reference_id, "amount": amount, "risk": "Alto", "reason": "Ajuste con monto revertido sin movimiento REV en Caja.", "status": "Pendiente", "created_at_utc": _now()})
        if cash_refs.get(expected_ref, 0) > 1:
            anomalies.append({"anomaly_id": f"ADA-{uuid4().hex[:8].upper()}", "adjustment_id": adjustment_id, "kind": row.get("kind", ""), "reference_id": reference_id, "amount": amount, "risk": "Alto", "reason": "Posible movimiento duplicado de reverso en Caja.", "status": "Pendiente", "created_at_utc": _now()})
        if not str(row.get("reason", "")).strip():
            anomalies.append({"anomaly_id": f"ADA-{uuid4().hex[:8].upper()}", "adjustment_id": adjustment_id, "kind": row.get("kind", ""), "reference_id": reference_id, "amount": amount, "risk": "Medio", "reason": "Ajuste sin motivo documentado.", "status": "Pendiente", "created_at_utc": _now()})
    return anomalies


def _period_reconciliation(period: str) -> dict[str, float]:
    adjustments = [row for row in _rows("adjustment_records") if str(row.get("created_at_utc", ""))[:7] == period]
    cash = [row for row in _adjustment_cash_rows() if str(row.get("created_at_utc", ""))[:7] == period]
    adjustment_total = sum(_num(row.get("amount")) for row in adjustments)
    cash_total = sum(_num(row.get("amount")) for row in cash)
    return {"adjustments": len(adjustments), "cash_movements": len(cash), "adjustment_total": adjustment_total, "cash_total": cash_total, "difference": cash_total - adjustment_total}


def _locked(period: str, locks: list[dict]) -> bool:
    return any(row.get("period") == period and row.get("active", True) for row in locks)


def _export(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Tipo", "Referencia", "Monto", "Riesgo", "Estado", "Solicitado", "Motivo"])
    for row in rows:
        writer.writerow([row.get("request_id", row.get("anomaly_id", "")), row.get("kind", ""), row.get("reference_id", ""), row.get("amount", 0), row.get("risk", ""), row.get("status", ""), row.get("requested_by", ""), row.get("reason", "")])
    return buffer.getvalue().encode("utf-8-sig")


def render_adjustments_governance() -> None:
    render_page_header("Anulaciones y ajustes", "Controla solicitudes, riesgos, evidencias, conciliación y bloqueos de ajustes.")

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_adjustments()
    finally:
        base.render_page_header = original_header

    requests = _rows("adjustment_requests")
    evidence = _rows("adjustment_evidence")
    reviews = _rows("adjustment_reviews")
    locks = _rows("adjustment_period_locks")
    anomalies_saved = _rows("adjustment_anomalies")
    operations = _available_operations()
    detected = _detect_anomalies()
    current_period = _period()
    rec = _period_reconciliation(current_period)
    pending = [row for row in requests if row.get("status") == "Pendiente"]
    approved = [row for row in requests if row.get("status") == "Aprobada"]

    st.divider()
    st.markdown("### Gobierno de anulaciones y ajustes")
    metrics = st.columns(5)
    metrics[0].metric("Solicitudes", str(len(pending)))
    metrics[1].metric("Aprobadas", str(len(approved)))
    metrics[2].metric("Anomalías", str(len(detected)))
    metrics[3].metric("Diferencia Caja", format_money(rec["difference"], get_currency()))
    metrics[4].metric("Periodo bloqueado", "Sí" if _locked(current_period, locks) else "No")

    request_tab, approval_tab, evidence_tab, reconcile_tab, anomaly_tab, lock_tab = st.tabs(("Solicitudes", "Aprobación", "Evidencias", "Conciliación", "Anomalías", "Bloqueo"))

    with request_tab:
        if not operations:
            st.info("No hay operaciones disponibles para solicitar anulación.")
        else:
            options = {f"{row.get('kind')} · {row.get('description')} · {format_money(_num(row.get('amount')), get_currency())} · {row.get('reference_id')}": row for row in operations[:300]}
            with st.form("adjustment_request_form", clear_on_submit=True):
                selected = st.selectbox("Operación", tuple(options.keys()))
                requested_by = st.text_input("Solicitado por")
                reason = st.text_area("Motivo", max_chars=700)
                expected_effect = st.text_area("Efecto esperado", max_chars=500)
                submitted = st.form_submit_button("Crear solicitud", type="primary", use_container_width=True)
            if submitted:
                if not requested_by.strip() or not reason.strip():
                    st.error("Solicitante y motivo son obligatorios.")
                else:
                    operation = options[selected]
                    risk, warnings = _risk(operation)
                    requests.append({"request_id": f"ADJ-{uuid4().hex[:8].upper()}", **operation, "risk": risk, "warnings": warnings, "requested_by": requested_by.strip(), "reason": reason.strip(), "expected_effect": expected_effect.strip(), "status": "Pendiente", "created_at_utc": _now()})
                    _save("adjustment_requests", requests)
                    st.rerun()
        st.download_button("Descargar solicitudes CSV", data=_export(requests), file_name="solicitudes_anulaciones_ajustes.csv", mime="text/csv", use_container_width=True, disabled=not requests)

    with approval_tab:
        if not pending:
            st.info("No hay solicitudes pendientes.")
        for request in reversed(pending):
            with st.container(border=True):
                st.markdown(f"**{request.get('request_id')} · {request.get('kind')} · {request.get('reference_id')}**")
                st.caption(f"Riesgo {request.get('risk')} · {format_money(_num(request.get('amount')), get_currency())}")
                for warning in request.get("warnings", [])[:5]:
                    st.warning(str(warning))
                with st.form(f"approve_adjustment_{request.get('request_id')}"):
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
                                current["decision_by"] = responsible.strip()
                                current["decision_note"] = note.strip()
                                current["decision_at_utc"] = _now()
                            changed.append(current)
                        _save("adjustment_requests", changed)
                        st.rerun()
        if approved:
            st.warning("La aplicación real de la anulación se realiza en las pestañas base de venta/compra para conservar las reglas originales de Caja e Inventario.")
        for request in reversed(approved[-50:]):
            st.write(f"**{request.get('request_id')} · {request.get('kind')} · {request.get('reference_id')}** — aprobado por {request.get('decision_by', '')}")

    with evidence_tab:
        adjustments = _rows("adjustment_records")
        if not adjustments:
            st.info("No hay ajustes para documentar.")
        else:
            options = {f"{row.get('kind')} · {row.get('reference_id')} · {format_money(_num(row.get('amount')), get_currency())}": row for row in adjustments[-300:]}
            with st.form("adjustment_evidence_form", clear_on_submit=True):
                selected = st.selectbox("Ajuste", tuple(options.keys()))
                evidence_type = st.selectbox("Tipo", ("Autorización", "Recibo", "Captura", "Nota interna", "Otro"))
                reference = st.text_input("Referencia")
                responsible = st.text_input("Responsable")
                note = st.text_area("Detalle", max_chars=600)
                submitted = st.form_submit_button("Guardar evidencia", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not note.strip():
                    st.error("Responsable y detalle son obligatorios.")
                else:
                    row = options[selected]
                    evidence.append({"evidence_id": f"ADE-{uuid4().hex[:8].upper()}", "adjustment_id": row.get("adjustment_id", ""), "kind": row.get("kind", ""), "reference_id": row.get("reference_id", ""), "evidence_type": evidence_type, "reference": reference.strip(), "responsible": responsible.strip(), "note": note.strip(), "created_at_utc": _now()})
                    _save("adjustment_evidence", evidence)
                    st.rerun()
        for item in reversed(evidence[-100:]):
            st.write(f"**{item.get('evidence_id')} · {item.get('kind')} · {item.get('reference_id')}** — {item.get('responsible')}: {item.get('note')}")

    with reconcile_tab:
        selected_period = st.text_input("Periodo", value=current_period, key="adjustment_reconcile_period")
        data = _period_reconciliation(selected_period)
        cols = st.columns(5)
        cols[0].metric("Ajustes", str(int(data["adjustments"])))
        cols[1].metric("Mov. Caja", str(int(data["cash_movements"])))
        cols[2].metric("Total ajustes", format_money(data["adjustment_total"], get_currency()))
        cols[3].metric("Total Caja", format_money(data["cash_total"], get_currency()))
        cols[4].metric("Diferencia", format_money(data["difference"], get_currency()))
        with st.form("adjustment_review_form", clear_on_submit=True):
            reviewer = st.text_input("Revisado por")
            conclusion = st.text_area("Conclusión", max_chars=700)
            submitted = st.form_submit_button("Guardar revisión", type="primary", use_container_width=True)
        if submitted:
            if not reviewer.strip() or not conclusion.strip():
                st.error("Revisor y conclusión son obligatorios.")
            else:
                reviews.append({"review_id": f"ADR-{uuid4().hex[:8].upper()}", "period": selected_period, **data, "reviewer": reviewer.strip(), "conclusion": conclusion.strip(), "created_at_utc": _now()})
                _save("adjustment_reviews", reviews)
                st.rerun()
        for review in reversed(reviews[-50:]):
            st.write(f"**{review.get('review_id')} · {review.get('period')}** · diferencia {format_money(_num(review.get('difference')), get_currency())} · {review.get('reviewer')}")

    with anomaly_tab:
        st.download_button("Descargar anomalías CSV", data=_export(detected), file_name=f"anomalias_ajustes_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not detected)
        if detected and st.button("Guardar anomalías detectadas", type="primary", use_container_width=True):
            anomalies_saved.extend(detected)
            _save("adjustment_anomalies", anomalies_saved)
            st.rerun()
        if not detected:
            st.success("No se detectan anomalías automáticas.")
        for item in detected[:100]:
            st.warning(f"{item.get('kind')} {item.get('reference_id')}: {item.get('reason')} · {format_money(_num(item.get('amount')), get_currency())}")

    with lock_tab:
        selected_period = st.text_input("Periodo a bloquear", value=current_period, key="adjustment_lock_period")
        is_locked = _locked(selected_period, locks)
        st.metric("Estado", "Bloqueado" if is_locked else "Abierto")
        with st.form("adjustment_lock_form", clear_on_submit=True):
            responsible = st.text_input("Responsable")
            reason = st.text_area("Motivo", max_chars=500)
            submitted = st.form_submit_button("Bloquear periodo", type="primary", use_container_width=True, disabled=is_locked)
        if submitted:
            if not responsible.strip() or not reason.strip():
                st.error("Responsable y motivo son obligatorios.")
            else:
                locks.append({"lock_id": f"ADL-{uuid4().hex[:8].upper()}", "period": selected_period, "responsible": responsible.strip(), "reason": reason.strip(), "active": True, "created_at_utc": _now()})
                _save("adjustment_period_locks", locks)
                st.rerun()
        for item in reversed(locks[-50:]):
            st.write(f"**{item.get('period')} · {'Activo' if item.get('active', True) else 'Liberado'}** — {item.get('responsible')}: {item.get('reason')}")

    render_info_card("Ajustes auditados", "Las anulaciones ahora tienen solicitud, riesgo, evidencia, conciliación y bloqueo por periodo.", "GOBIERNO")


app_shell.FUNCTIONAL_MODULES["Anulaciones y ajustes"] = render_adjustments_governance
