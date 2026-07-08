"""Reapertura avanzada de cierres de caja con aprobación, reversión y auditoría."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, cash_closing_reopen as base, financial_control, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("cash_reopen_requests", "Solicitudes de reapertura de cierre de caja"),
        ("cash_reopen_audit", "Auditoría de reaperturas de caja"),
        ("cash_reopen_reviews", "Revisiones de reaperturas de caja"),
        ("cash_reopen_rollbacks", "Reversiones de reapertura de caja"),
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


def _active_closings(closings: list[dict]) -> list[dict]:
    return base._active_closings(closings)


def _reopened(closings: list[dict]) -> list[dict]:
    return [row for row in closings if row.get("reopened")]


def _latest_active(closings: list[dict]) -> dict | None:
    active = _active_closings(closings)
    return dict(active[-1]) if active else None


def _reopen_risk(closing: dict) -> tuple[str, list[str]]:
    warnings: list[str] = []
    difference = abs(_num(closing.get("difference")))
    movements = int(_num(closing.get("movement_count", len(closing.get("movement_ids", [])))))
    closed_at = _dt(closing.get("closed_at_utc", closing.get("created_at_utc", closing.get("closing_date"))))
    age_days = (datetime.now() - closed_at).days if closed_at else 0
    if difference >= 10:
        warnings.append("La diferencia original del cierre es alta.")
    if movements >= 30:
        warnings.append("El cierre incluye muchos movimientos.")
    if age_days >= 7:
        warnings.append("El cierre tiene más de 7 días cerrado.")
    if closing.get("reconciliation_status") == "Conciliado":
        warnings.append("El cierre aparece como conciliado.")
    if len(warnings) >= 2 or difference >= 20:
        return "Alto", warnings
    if warnings:
        return "Medio", warnings
    return "Bajo", warnings


def _audit(action: str, closing_id: str, responsible: str, note: str) -> None:
    rows = _rows("cash_reopen_audit")
    rows.append({
        "audit_id": f"RCA-{uuid4().hex[:8].upper()}",
        "action": action,
        "closing_id": closing_id,
        "responsible": responsible.strip() or "Sin asignar",
        "note": note.strip(),
        "created_at_utc": _now(),
    })
    _save("cash_reopen_audit", rows)


def _apply_reopen(closing_id: str, responsible: str, reason: str, request_id: str = "") -> None:
    closings = _rows("cash_closings")
    changed = []
    for closing in closings:
        row = dict(closing)
        if str(row.get("closing_id", "")) == closing_id:
            row["reopened"] = True
            row["reopened_at_utc"] = _now()
            row["reopened_by"] = responsible.strip() or "Sin asignar"
            row["reopen_reason"] = reason.strip() or "Corrección de cierre"
            row["reopen_request_id"] = request_id
            row["reconciliation_status"] = "Reabierto"
        changed.append(row)
    _save("cash_closings", changed)
    _audit("Reapertura aplicada", closing_id, responsible, reason)


def _rollback_reopen(closing_id: str, responsible: str, reason: str) -> None:
    closings = _rows("cash_closings")
    changed = []
    for closing in closings:
        row = dict(closing)
        if str(row.get("closing_id", "")) == closing_id:
            row["reopened"] = False
            row["reopen_rollback_at_utc"] = _now()
            row["reopen_rollback_by"] = responsible.strip() or "Sin asignar"
            row["reopen_rollback_reason"] = reason.strip()
            row["reconciliation_status"] = "Cerrado"
        changed.append(row)
    _save("cash_closings", changed)
    rollbacks = _rows("cash_reopen_rollbacks")
    rollbacks.append({
        "rollback_id": f"RRB-{uuid4().hex[:8].upper()}",
        "closing_id": closing_id,
        "responsible": responsible.strip() or "Sin asignar",
        "reason": reason.strip(),
        "created_at_utc": _now(),
    })
    _save("cash_reopen_rollbacks", rollbacks)
    _audit("Reapertura revertida", closing_id, responsible, reason)


def _export(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Cierre", "Estado", "Riesgo", "Solicitado por", "Aprobado por", "Motivo", "Fecha"])
    for row in rows:
        writer.writerow([
            row.get("request_id", ""), row.get("closing_id", ""), row.get("status", ""), row.get("risk", ""),
            row.get("requested_by", ""), row.get("approved_by", ""), row.get("reason", ""), row.get("created_at_utc", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_cash_closing_reopen_control() -> None:
    base.activate_closing_reopen_support()
    financial_control._closed_ids = base._closed_ids
    financial_control._opening_by_method = base._opening_by_method

    render_page_header(
        "Reabrir cierre de caja",
        "Gestiona reaperturas con solicitud, aprobación, riesgo, auditoría y reversión segura.",
    )

    closings = _rows("cash_closings")
    requests = _rows("cash_reopen_requests")
    reviews = _rows("cash_reopen_reviews")
    audit = _rows("cash_reopen_audit")
    rollbacks = _rows("cash_reopen_rollbacks")
    latest = _latest_active(closings)
    reopened = _reopened(closings)
    pending = [row for row in requests if row.get("status") == "Pendiente"]
    approved_waiting = [row for row in requests if row.get("status") == "Aprobada"]

    metrics = st.columns(5)
    metrics[0].metric("Cierres activos", str(len(_active_closings(closings))))
    metrics[1].metric("Reabiertos", str(len(reopened)))
    metrics[2].metric("Solicitudes pendientes", str(len(pending)))
    metrics[3].metric("Aprobadas sin aplicar", str(len(approved_waiting)))
    metrics[4].metric("Reversiones", str(len(rollbacks)))

    request_tab, approval_tab, apply_tab, rollback_tab, audit_tab = st.tabs(("Solicitud", "Aprobación", "Aplicar", "Reversión", "Auditoría"))

    with request_tab:
        if not latest:
            st.info("No hay cierres activos para solicitar reapertura.")
        else:
            risk, warnings = _reopen_risk(latest)
            with st.container(border=True):
                st.markdown(f"**Último cierre activo · {latest.get('closing_date', '')}**")
                cols = st.columns(5)
                cols[0].metric("Riesgo", risk)
                cols[1].metric("Esperado", format_money(_num(latest.get("expected_balance")), get_currency()))
                cols[2].metric("Contado", format_money(_num(latest.get("counted_cash")), get_currency()))
                cols[3].metric("Diferencia", format_money(_num(latest.get("difference")), get_currency()))
                cols[4].metric("Movimientos", str(latest.get("movement_count", len(latest.get("movement_ids", [])))))
                for warning in warnings:
                    st.warning(warning)
            with st.form("cash_reopen_request_form", clear_on_submit=True):
                requested_by = st.text_input("Solicitado por")
                reason = st.text_area("Motivo detallado", max_chars=700)
                expected_fix = st.text_area("Qué se va a corregir", max_chars=700)
                urgent = st.checkbox("Es urgente")
                submitted = st.form_submit_button("Crear solicitud de reapertura", type="primary", use_container_width=True)
            if submitted:
                if not requested_by.strip() or not reason.strip() or not expected_fix.strip():
                    st.error("Solicitante, motivo y corrección esperada son obligatorios.")
                else:
                    request_id = f"RCR-{uuid4().hex[:8].upper()}"
                    requests.append({
                        "request_id": request_id,
                        "closing_id": str(latest.get("closing_id", "")),
                        "closing_date": str(latest.get("closing_date", "")),
                        "risk": risk,
                        "warnings": warnings,
                        "requested_by": requested_by.strip(),
                        "reason": reason.strip(),
                        "expected_fix": expected_fix.strip(),
                        "urgent": bool(urgent),
                        "status": "Pendiente",
                        "created_at_utc": _now(),
                    })
                    _save("cash_reopen_requests", requests)
                    _audit("Solicitud creada", str(latest.get("closing_id", "")), requested_by, reason)
                    st.rerun()
        st.download_button("Descargar solicitudes CSV", data=_export(requests), file_name="solicitudes_reapertura_caja.csv", mime="text/csv", use_container_width=True, disabled=not requests)

    with approval_tab:
        if not pending:
            st.info("No hay solicitudes pendientes.")
        for request in reversed(pending):
            with st.container(border=True):
                st.markdown(f"**{request.get('request_id', '')} · cierre {request.get('closing_id', '')}**")
                st.caption(f"Riesgo {request.get('risk', 'Bajo')} · {request.get('requested_by', '')} · {request.get('created_at_utc', '')}")
                st.write(str(request.get("reason", "")))
                with st.form(f"approve_reopen_{request.get('request_id')}"):
                    decision = st.selectbox("Decisión", ("Aprobar", "Rechazar"), key=f"decision_{request.get('request_id')}")
                    approved_by = st.text_input("Responsable de decisión", key=f"approver_{request.get('request_id')}")
                    note = st.text_area("Nota", max_chars=500, key=f"note_{request.get('request_id')}")
                    submitted = st.form_submit_button("Guardar decisión", type="primary", use_container_width=True)
                if submitted:
                    if not approved_by.strip():
                        st.error("Indica responsable de la decisión.")
                    else:
                        changed = []
                        for row in requests:
                            current = dict(row)
                            if current.get("request_id") == request.get("request_id"):
                                current["status"] = "Aprobada" if decision == "Aprobar" else "Rechazada"
                                current["approved_by"] = approved_by.strip() if decision == "Aprobar" else ""
                                current["rejected_by"] = approved_by.strip() if decision == "Rechazar" else ""
                                current["decision_note"] = note.strip()
                                current["decision_at_utc"] = _now()
                            changed.append(current)
                        _save("cash_reopen_requests", changed)
                        _audit(f"Solicitud {decision.lower()}", str(request.get("closing_id", "")), approved_by, note)
                        st.rerun()

    with apply_tab:
        approved = [row for row in requests if row.get("status") == "Aprobada"]
        if not approved:
            st.info("No hay solicitudes aprobadas para aplicar.")
        for request in reversed(approved):
            with st.container(border=True):
                st.markdown(f"**Aplicar {request.get('request_id', '')} · cierre {request.get('closing_id', '')}**")
                st.caption(str(request.get("expected_fix", "")))
                with st.form(f"apply_reopen_{request.get('request_id')}"):
                    responsible = st.text_input("Responsable de aplicación", key=f"apply_by_{request.get('request_id')}")
                    confirmation = st.text_input("Escribe REABRIR para confirmar", max_chars=20, key=f"confirm_{request.get('request_id')}")
                    submitted = st.form_submit_button("Aplicar reapertura", type="primary", use_container_width=True)
                if submitted:
                    if confirmation.strip().upper() != "REABRIR" or not responsible.strip():
                        st.error("Responsable y confirmación REABRIR son obligatorios.")
                    else:
                        _apply_reopen(str(request.get("closing_id", "")), responsible, str(request.get("reason", "")), str(request.get("request_id", "")))
                        changed = []
                        for row in requests:
                            current = dict(row)
                            if current.get("request_id") == request.get("request_id"):
                                current["status"] = "Aplicada"
                                current["applied_by"] = responsible.strip()
                                current["applied_at_utc"] = _now()
                            changed.append(current)
                        _save("cash_reopen_requests", changed)
                        st.success("Reapertura aplicada.")
                        st.rerun()

    with rollback_tab:
        if not reopened:
            st.info("No hay reaperturas para revertir.")
        for closing in reversed(reopened[-50:]):
            with st.container(border=True):
                st.markdown(f"**Cierre reabierto {closing.get('closing_id', '')}**")
                st.caption(f"{closing.get('reopened_by', '')} · {closing.get('reopened_at_utc', '')} · {closing.get('reopen_reason', '')}")
                with st.form(f"rollback_reopen_{closing.get('closing_id')}"):
                    responsible = st.text_input("Responsable", key=f"rollback_by_{closing.get('closing_id')}")
                    reason = st.text_area("Motivo de reversión", max_chars=400, key=f"rollback_reason_{closing.get('closing_id')}")
                    confirmed = st.checkbox("Confirmo que deseo dejar el cierre como cerrado nuevamente", key=f"rollback_confirm_{closing.get('closing_id')}")
                    submitted = st.form_submit_button("Revertir reapertura", type="primary", use_container_width=True)
                if submitted:
                    if not responsible.strip() or not reason.strip() or not confirmed:
                        st.error("Responsable, motivo y confirmación son obligatorios.")
                    else:
                        _rollback_reopen(str(closing.get("closing_id", "")), responsible, reason)
                        st.rerun()

    with audit_tab:
        if not audit:
            st.info("No hay auditoría de reaperturas.")
        for entry in reversed(audit[-150:]):
            st.write(f"**{entry.get('action', '')}** · cierre {entry.get('closing_id', '')} · {entry.get('responsible', '')} · {entry.get('created_at_utc', '')} — {entry.get('note', '')}")
        st.markdown("#### Revisiones posteriores")
        with st.form("reopen_review_form", clear_on_submit=True):
            reviewer = st.text_input("Revisado por")
            note = st.text_area("Conclusión", max_chars=600)
            submitted = st.form_submit_button("Guardar revisión", type="primary", use_container_width=True)
        if submitted:
            if not reviewer.strip() or not note.strip():
                st.error("Revisor y conclusión son obligatorios.")
            else:
                reviews.append({
                    "review_id": f"RRV-{uuid4().hex[:8].upper()}",
                    "reviewer": reviewer.strip(),
                    "note": note.strip(),
                    "created_at_utc": _now(),
                })
                _save("cash_reopen_reviews", reviews)
                st.rerun()
        for review in reversed(reviews[-50:]):
            st.write(f"**{review.get('review_id', '')}** · {review.get('reviewer', '')} · {review.get('note', '')}")

    render_info_card(
        "Reapertura gobernada",
        "La reapertura deja de ser una acción directa: ahora pasa por solicitud, aprobación, aplicación, auditoría y reversión.",
        "CONTROL DE CIERRES",
    )


app_shell.FUNCTIONAL_MODULES["Reabrir cierre de caja"] = render_cash_closing_reopen_control
