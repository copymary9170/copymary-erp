"""Gobierno avanzado del historial de comisiones."""

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, commission_history_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("commission_history_anomalies", "Anomalías del historial de comisiones"),
        ("commission_history_evidence", "Evidencias del historial de comisiones"),
        ("commission_history_period_locks", "Bloqueos de periodo del historial de comisiones"),
        ("commission_history_reconciliations", "Conciliaciones del historial de comisiones"),
        ("commission_history_support_cases", "Casos de soporte del historial de comisiones"),
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


def _history_rows() -> list[dict]:
    return base._history_rows()


def _periods(rows: list[dict]) -> list[str]:
    return sorted({str(row.get("period", "Sin fecha")) for row in rows}, reverse=True)


def _period_locked(period: str, locks: list[dict]) -> bool:
    return any(row.get("period") == period and row.get("active", True) for row in locks)


def _detect_anomalies(rows: list[dict]) -> list[dict]:
    anomalies: list[dict] = []
    key_counter = Counter((row.get("kind"), row.get("member_id"), row.get("reference"), round(_num(row.get("amount")), 2)) for row in rows)
    for row in rows:
        amount = _num(row.get("amount"))
        key = (row.get("kind"), row.get("member_id"), row.get("reference"), round(amount, 2))
        if key_counter[key] > 1 and row.get("reference"):
            anomalies.append({
                "anomaly_id": f"CHA-{uuid4().hex[:8].upper()}",
                "history_id": row.get("id", ""),
                "period": row.get("period", ""),
                "member": row.get("member", ""),
                "kind": row.get("kind", ""),
                "amount": amount,
                "risk": "Alto",
                "reason": "Posible movimiento duplicado por tipo, colaborador, referencia y monto.",
                "status": "Pendiente",
                "created_at_utc": _now(),
            })
        if row.get("kind") == "Pago de comisión" and abs(amount) > 0 and not row.get("reference"):
            anomalies.append({
                "anomaly_id": f"CHA-{uuid4().hex[:8].upper()}",
                "history_id": row.get("id", ""),
                "period": row.get("period", ""),
                "member": row.get("member", ""),
                "kind": row.get("kind", ""),
                "amount": amount,
                "risk": "Medio",
                "reason": "Pago de comisión sin referencia registrada.",
                "status": "Pendiente",
                "created_at_utc": _now(),
            })
        if row.get("kind") == "Comisión generada" and amount <= 0:
            anomalies.append({
                "anomaly_id": f"CHA-{uuid4().hex[:8].upper()}",
                "history_id": row.get("id", ""),
                "period": row.get("period", ""),
                "member": row.get("member", ""),
                "kind": row.get("kind", ""),
                "amount": amount,
                "risk": "Alto",
                "reason": "Comisión generada con monto cero o negativo.",
                "status": "Pendiente",
                "created_at_utc": _now(),
            })
    return anomalies


def _period_reconciliation(rows: list[dict], period: str) -> dict[str, float]:
    scoped = [row for row in rows if row.get("period") == period]
    generated = sum(_num(row.get("amount")) for row in scoped if row.get("kind") == "Comisión generada")
    paid = sum(abs(_num(row.get("amount"))) for row in scoped if row.get("kind") == "Pago de comisión")
    receipts = sum(_num(row.get("amount")) for row in scoped if row.get("kind") == "Recibo emitido")
    deductions = sum(abs(_num(row.get("amount"))) for row in scoped if row.get("kind") in {"Anticipo", "Ajuste / penalización"})
    expected_pending = max(generated - paid - deductions, 0.0)
    receipt_gap = receipts - expected_pending
    return {"generated": generated, "paid": paid, "receipts": receipts, "deductions": deductions, "expected_pending": expected_pending, "receipt_gap": receipt_gap}


def _export_anomalies(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Periodo", "Colaborador", "Tipo", "Monto", "Riesgo", "Motivo", "Estado"])
    for row in rows:
        writer.writerow([row.get("anomaly_id", ""), row.get("period", ""), row.get("member", ""), row.get("kind", ""), row.get("amount", 0), row.get("risk", ""), row.get("reason", ""), row.get("status", "")])
    return buffer.getvalue().encode("utf-8-sig")


def render_commission_history_governance() -> None:
    render_page_header("Historial de comisiones", "Audita anomalías, evidencias, conciliación y bloqueo de periodos.")

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_commission_history_plus()
    finally:
        base.render_page_header = original_header

    rows = _history_rows()
    periods = _periods(rows)
    current_period = periods[0] if periods else f"{date.today().year:04d}-{date.today().month:02d}"
    anomalies_saved = _rows("commission_history_anomalies")
    evidence = _rows("commission_history_evidence")
    locks = _rows("commission_history_period_locks")
    reconciliations = _rows("commission_history_reconciliations")
    cases = _rows("commission_history_support_cases")
    detected = _detect_anomalies(rows)
    open_cases = [row for row in cases if row.get("status") != "Cerrado"]
    rec = _period_reconciliation(rows, current_period)

    st.divider()
    st.markdown("### Gobierno del historial")
    metrics = st.columns(5)
    metrics[0].metric("Anomalías detectadas", str(len(detected)))
    metrics[1].metric("Casos abiertos", str(len(open_cases)))
    metrics[2].metric("Evidencias", str(len(evidence)))
    metrics[3].metric("Brecha recibos", format_money(rec["receipt_gap"], get_currency()))
    metrics[4].metric("Periodo bloqueado", "Sí" if _period_locked(current_period, locks) else "No")

    anomaly_tab, evidence_tab, reconcile_tab, lock_tab, cases_tab = st.tabs(("Anomalías", "Evidencias", "Conciliación", "Bloqueo", "Casos"))

    with anomaly_tab:
        st.download_button("Descargar anomalías CSV", data=_export_anomalies(detected), file_name=f"anomalias_comisiones_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not detected)
        if detected and st.button("Guardar anomalías detectadas", type="primary", use_container_width=True):
            anomalies_saved.extend(detected)
            _save("commission_history_anomalies", anomalies_saved)
            st.rerun()
        if not detected:
            st.success("No se detectan anomalías automáticas en el historial actual.")
        for item in detected[:100]:
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{item.get('reason', '')}**")
                cols[0].caption(f"{item.get('period', '')} · {item.get('member', '')} · {item.get('kind', '')}")
                cols[1].metric("Monto", format_money(_num(item.get("amount")), get_currency()))
                cols[2].metric("Riesgo", str(item.get("risk", "")))

    with evidence_tab:
        if not rows:
            st.info("No hay movimientos para asociar evidencias.")
        else:
            options = {f"{row.get('kind')} · {row.get('member')} · {row.get('reference')} · {format_money(_num(row.get('amount')), get_currency())}": row for row in rows[:300]}
            with st.form("commission_evidence_form", clear_on_submit=True):
                selected = st.selectbox("Movimiento", tuple(options.keys()))
                evidence_type = st.selectbox("Tipo de evidencia", ("Recibo", "Captura", "Nota interna", "Aprobación", "Otro"))
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
                        "evidence_id": f"CHEV-{uuid4().hex[:8].upper()}",
                        "history_id": row.get("id", ""),
                        "period": row.get("period", ""),
                        "member": row.get("member", ""),
                        "evidence_type": evidence_type,
                        "reference": reference.strip(),
                        "responsible": responsible.strip(),
                        "note": note.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("commission_history_evidence", evidence)
                    st.rerun()
        for item in reversed(evidence[-100:]):
            st.write(f"**{item.get('evidence_id', '')} · {item.get('evidence_type', '')}** · {item.get('member', '')} · {item.get('responsible', '')}: {item.get('note', '')}")

    with reconcile_tab:
        selected_period = st.selectbox("Periodo a conciliar", tuple(periods) if periods else (current_period,))
        period_rec = _period_reconciliation(rows, selected_period)
        cols = st.columns(5)
        cols[0].metric("Generado", format_money(period_rec["generated"], get_currency()))
        cols[1].metric("Pagado", format_money(period_rec["paid"], get_currency()))
        cols[2].metric("Deducciones", format_money(period_rec["deductions"], get_currency()))
        cols[3].metric("Pendiente esperado", format_money(period_rec["expected_pending"], get_currency()))
        cols[4].metric("Brecha recibos", format_money(period_rec["receipt_gap"], get_currency()))
        with st.form("commission_history_reconciliation_form", clear_on_submit=True):
            responsible = st.text_input("Responsable")
            conclusion = st.text_area("Conclusión", max_chars=700)
            submitted = st.form_submit_button("Guardar conciliación", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip() or not conclusion.strip():
                st.error("Responsable y conclusión son obligatorios.")
            else:
                reconciliations.append({"reconciliation_id": f"CHRZ-{uuid4().hex[:8].upper()}", "period": selected_period, **period_rec, "responsible": responsible.strip(), "conclusion": conclusion.strip(), "created_at_utc": _now()})
                _save("commission_history_reconciliations", reconciliations)
                st.rerun()
        for item in reversed(reconciliations[-50:]):
            st.write(f"**{item.get('reconciliation_id', '')} · {item.get('period', '')}** · brecha {format_money(_num(item.get('receipt_gap')), get_currency())} · {item.get('responsible', '')}")

    with lock_tab:
        selected_period = st.selectbox("Periodo", tuple(periods) if periods else (current_period,), key="lock_period")
        locked = _period_locked(selected_period, locks)
        st.metric("Estado", "Bloqueado" if locked else "Abierto")
        with st.form("commission_period_lock_form", clear_on_submit=True):
            responsible = st.text_input("Responsable")
            reason = st.text_area("Motivo", max_chars=500)
            submitted = st.form_submit_button("Bloquear periodo", type="primary", use_container_width=True, disabled=locked)
        if submitted:
            if not responsible.strip() or not reason.strip():
                st.error("Responsable y motivo son obligatorios.")
            else:
                locks.append({"lock_id": f"CHL-{uuid4().hex[:8].upper()}", "period": selected_period, "responsible": responsible.strip(), "reason": reason.strip(), "active": True, "created_at_utc": _now()})
                _save("commission_history_period_locks", locks)
                st.rerun()
        for item in reversed(locks[-50:]):
            st.write(f"**{item.get('period', '')} · {'Activo' if item.get('active', True) else 'Liberado'}** — {item.get('responsible', '')}: {item.get('reason', '')}")

    with cases_tab:
        with st.form("commission_support_case_form", clear_on_submit=True):
            case_type = st.selectbox("Tipo", ("Diferencia", "Doble pago", "Falta evidencia", "Reclamo", "Otro"))
            period = st.selectbox("Periodo", tuple(periods) if periods else (current_period,), key="case_period")
            responsible = st.text_input("Responsable")
            description = st.text_area("Descripción", max_chars=700)
            submitted = st.form_submit_button("Abrir caso", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip() or not description.strip():
                st.error("Responsable y descripción son obligatorios.")
            else:
                cases.append({"case_id": f"CHC-{uuid4().hex[:8].upper()}", "case_type": case_type, "period": period, "responsible": responsible.strip(), "description": description.strip(), "status": "Abierto", "created_at_utc": _now()})
                _save("commission_history_support_cases", cases)
                st.rerun()
        for item in reversed(cases[-100:]):
            with st.container(border=True):
                st.markdown(f"**{item.get('case_id', '')} · {item.get('case_type', '')} · {item.get('status', '')}**")
                st.caption(f"{item.get('period', '')} · {item.get('responsible', '')}")
                st.write(item.get("description", ""))
                if item.get("status") != "Cerrado" and st.button("Cerrar caso", key=f"close_commission_case_{item.get('case_id')}", use_container_width=True):
                    changed = []
                    for case in cases:
                        current = dict(case)
                        if current.get("case_id") == item.get("case_id"):
                            current["status"] = "Cerrado"
                            current["closed_at_utc"] = _now()
                        changed.append(current)
                    _save("commission_history_support_cases", changed)
                    st.rerun()

    render_info_card("Historial auditado", "El historial ahora puede detectar anomalías, exigir evidencia, conciliar periodos y bloquear cierres revisados.", "GOBIERNO")


app_shell.FUNCTIONAL_MODULES["Historial de comisiones"] = render_commission_history_governance
