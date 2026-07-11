"""Gobierno posterior para reversos de pagos."""

from collections import Counter
from datetime import date, datetime, timedelta
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, payment_reversals_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("payment_reversal_sla_rules", "Reglas SLA de reversos de pagos"),
        ("payment_reversal_reconciliations", "Conciliaciones de reversos de pagos"),
        ("payment_reversal_support_cases", "Casos de soporte de reversos de pagos"),
        ("payment_reversal_period_locks", "Bloqueos de periodos de reversos"),
        ("payment_reversal_anomalies", "Anomalías de reversos de pagos"),
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


def _period() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def _rules() -> dict:
    defaults = {"high_hours": 4, "medium_hours": 12, "low_hours": 24, "max_open_cases": 0}
    rows = _rows("payment_reversal_sla_rules")
    if rows:
        defaults.update(rows[0])
    return defaults


def _risk_hours(risk: str, rules: dict) -> int:
    if risk == "Alto":
        return int(_num(rules.get("high_hours"), 4))
    if risk == "Medio":
        return int(_num(rules.get("medium_hours"), 12))
    return int(_num(rules.get("low_hours"), 24))


def _due_at(request: dict, rules: dict) -> datetime | None:
    created = _dt(request.get("created_at_utc"))
    if created is None:
        return None
    return created + timedelta(hours=_risk_hours(str(request.get("risk", "Bajo")), rules))


def _reversed_payments() -> list[dict]:
    output: list[dict] = []
    for key, kind in (("payment_records", "Cliente"), ("supplier_payment_records", "Proveedor"), ("team_payments", "Equipo")):
        for payment in _rows(key):
            if payment.get("reversed"):
                output.append({"kind": kind, "source_key": key, **payment})
    return sorted(output, key=lambda row: str(row.get("reversed_at_utc", "")), reverse=True)


def _cash_reversals() -> list[dict]:
    return [row for row in _rows("cash_movements") if str(row.get("reference", "")).startswith("REV-") or row.get("source_reversal")]


def _detect_anomalies(reversed_payments: list[dict], cash_rows: list[dict]) -> list[dict]:
    anomalies: list[dict] = []
    cash_refs = Counter(str(row.get("reference", "")) for row in cash_rows)
    for payment in reversed_payments:
        payment_id = str(payment.get("payment_id", ""))
        expected_ref = f"REV-{payment_id}"
        if cash_refs.get(expected_ref, 0) == 0:
            anomalies.append({
                "anomaly_id": f"PRA-{uuid4().hex[:8].upper()}",
                "kind": payment.get("kind", ""),
                "payment_id": payment_id,
                "amount": _num(payment.get("amount")),
                "risk": "Alto",
                "reason": "Pago marcado como reversado sin movimiento contrario en Caja.",
                "status": "Pendiente",
                "created_at_utc": _now(),
            })
        elif cash_refs.get(expected_ref, 0) > 1:
            anomalies.append({
                "anomaly_id": f"PRA-{uuid4().hex[:8].upper()}",
                "kind": payment.get("kind", ""),
                "payment_id": payment_id,
                "amount": _num(payment.get("amount")),
                "risk": "Alto",
                "reason": "Posible reverso duplicado en Caja.",
                "status": "Pendiente",
                "created_at_utc": _now(),
            })
        if not str(payment.get("reversal_reason", "")).strip():
            anomalies.append({
                "anomaly_id": f"PRA-{uuid4().hex[:8].upper()}",
                "kind": payment.get("kind", ""),
                "payment_id": payment_id,
                "amount": _num(payment.get("amount")),
                "risk": "Medio",
                "reason": "Reverso sin motivo documentado.",
                "status": "Pendiente",
                "created_at_utc": _now(),
            })
    return anomalies


def _period_reconciliation(period: str, reversed_payments: list[dict], cash_rows: list[dict]) -> dict[str, float]:
    payments = [row for row in reversed_payments if str(row.get("reversed_at_utc", row.get("payment_date", "")))[:7] == period]
    cash = [row for row in cash_rows if str(row.get("created_at_utc", ""))[:7] == period]
    payment_total = sum(_num(row.get("amount")) for row in payments)
    cash_total = sum(_num(row.get("amount")) for row in cash)
    return {"payments": len(payments), "cash_movements": len(cash), "payment_total": payment_total, "cash_total": cash_total, "difference": cash_total - payment_total}


def _locked(period: str, locks: list[dict]) -> bool:
    return any(row.get("period") == period and row.get("active", True) for row in locks)


def _export_anomalies(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Tipo", "Pago", "Monto", "Riesgo", "Motivo", "Estado"])
    for row in rows:
        writer.writerow([row.get("anomaly_id", ""), row.get("kind", ""), row.get("payment_id", ""), row.get("amount", 0), row.get("risk", ""), row.get("reason", ""), row.get("status", "")])
    return buffer.getvalue().encode("utf-8-sig")


def render_payment_reversals_governance() -> None:
    render_page_header("Reversos de pagos", "Añade SLA, conciliación con Caja, anomalías, bloqueos y casos de soporte.")

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_payment_reversals_plus()
    finally:
        base.render_page_header = original_header

    requests = _rows("payment_reversal_requests")
    rules = _rules()
    reversed_payments = _reversed_payments()
    cash_rows = _cash_reversals()
    anomalies_saved = _rows("payment_reversal_anomalies")
    reconciliations = _rows("payment_reversal_reconciliations")
    cases = _rows("payment_reversal_support_cases")
    locks = _rows("payment_reversal_period_locks")
    period = _period()
    active_requests = [row for row in requests if row.get("status") in {"Pendiente", "Aprobada"}]
    overdue = [row for row in active_requests if (due := _due_at(row, rules)) is not None and due < datetime.now()]
    open_cases = [row for row in cases if row.get("status") != "Cerrado"]
    detected = _detect_anomalies(reversed_payments, cash_rows)
    reconciliation = _period_reconciliation(period, reversed_payments, cash_rows)

    st.divider()
    st.markdown("### Gobierno posterior de reversos")
    metrics = st.columns(5)
    metrics[0].metric("SLA vencidos", str(len(overdue)))
    metrics[1].metric("Anomalías", str(len(detected)))
    metrics[2].metric("Casos abiertos", str(len(open_cases)))
    metrics[3].metric("Diferencia Caja", format_money(reconciliation["difference"], get_currency()))
    metrics[4].metric("Periodo bloqueado", "Sí" if _locked(period, locks) else "No")

    if overdue:
        st.error("Hay solicitudes de reverso vencidas según SLA.")
    if detected:
        st.warning("Hay anomalías automáticas para revisar.")

    sla_tab, reconcile_tab, anomalies_tab, lock_tab, cases_tab = st.tabs(("SLA", "Conciliación", "Anomalías", "Bloqueo", "Casos"))

    with sla_tab:
        with st.form("payment_reversal_sla_rules_form"):
            cols = st.columns(4)
            high = cols[0].number_input("Riesgo alto horas", min_value=1, value=int(_num(rules.get("high_hours"), 4)), step=1)
            medium = cols[1].number_input("Riesgo medio horas", min_value=1, value=int(_num(rules.get("medium_hours"), 12)), step=1)
            low = cols[2].number_input("Riesgo bajo horas", min_value=1, value=int(_num(rules.get("low_hours"), 24)), step=1)
            max_cases = cols[3].number_input("Máx. casos abiertos", min_value=0, value=int(_num(rules.get("max_open_cases"), 0)), step=1)
            submitted = st.form_submit_button("Guardar reglas", type="primary", use_container_width=True)
        if submitted:
            _save("payment_reversal_sla_rules", [{"high_hours": int(high), "medium_hours": int(medium), "low_hours": int(low), "max_open_cases": int(max_cases), "updated_at_utc": _now()}])
            st.rerun()
        for request in reversed(active_requests[-100:]):
            due = _due_at(request, rules)
            late = due is not None and due < datetime.now()
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{request.get('request_id', '')} · {request.get('kind', '')} · {request.get('payment_id', '')}**")
                cols[0].caption(f"Riesgo {request.get('risk', '')} · vence {due.isoformat() if due else 'Sin fecha'}")
                cols[1].metric("Estado", str(request.get("status", "")))
                cols[2].metric("SLA", "Vencido" if late else "Activo")

    with reconcile_tab:
        selected_period = st.text_input("Periodo", value=period, key="payment_reversal_reconcile_period")
        data = _period_reconciliation(selected_period, reversed_payments, cash_rows)
        cols = st.columns(5)
        cols[0].metric("Pagos reversados", str(int(data["payments"])))
        cols[1].metric("Mov. Caja", str(int(data["cash_movements"])))
        cols[2].metric("Total pagos", format_money(data["payment_total"], get_currency()))
        cols[3].metric("Total Caja", format_money(data["cash_total"], get_currency()))
        cols[4].metric("Diferencia", format_money(data["difference"], get_currency()))
        with st.form("payment_reversal_reconciliation_form", clear_on_submit=True):
            responsible = st.text_input("Responsable")
            conclusion = st.text_area("Conclusión", max_chars=700)
            submitted = st.form_submit_button("Guardar conciliación", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip() or not conclusion.strip():
                st.error("Responsable y conclusión son obligatorios.")
            else:
                reconciliations.append({"reconciliation_id": f"PRC-{uuid4().hex[:8].upper()}", "period": selected_period, **data, "responsible": responsible.strip(), "conclusion": conclusion.strip(), "created_at_utc": _now()})
                _save("payment_reversal_reconciliations", reconciliations)
                st.rerun()
        for item in reversed(reconciliations[-50:]):
            st.write(f"**{item.get('reconciliation_id')} · {item.get('period')}** · diferencia {format_money(_num(item.get('difference')), get_currency())} · {item.get('responsible')}")

    with anomalies_tab:
        st.download_button("Descargar anomalías CSV", data=_export_anomalies(detected), file_name=f"anomalias_reversos_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not detected)
        if detected and st.button("Guardar anomalías detectadas", type="primary", use_container_width=True):
            anomalies_saved.extend(detected)
            _save("payment_reversal_anomalies", anomalies_saved)
            st.rerun()
        if not detected:
            st.success("No se detectan anomalías automáticas.")
        for item in detected[:100]:
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{item.get('reason', '')}**")
                cols[0].caption(f"{item.get('kind', '')} · {item.get('payment_id', '')}")
                cols[1].metric("Monto", format_money(_num(item.get("amount")), get_currency()))
                cols[2].metric("Riesgo", str(item.get("risk", "")))

    with lock_tab:
        selected_period = st.text_input("Periodo a bloquear", value=period, key="payment_reversal_lock_period")
        is_locked = _locked(selected_period, locks)
        st.metric("Estado", "Bloqueado" if is_locked else "Abierto")
        with st.form("payment_reversal_lock_form", clear_on_submit=True):
            responsible = st.text_input("Responsable")
            reason = st.text_area("Motivo", max_chars=500)
            submitted = st.form_submit_button("Bloquear periodo", type="primary", use_container_width=True, disabled=is_locked)
        if submitted:
            if not responsible.strip() or not reason.strip():
                st.error("Responsable y motivo son obligatorios.")
            else:
                locks.append({"lock_id": f"PRL-{uuid4().hex[:8].upper()}", "period": selected_period, "responsible": responsible.strip(), "reason": reason.strip(), "active": True, "created_at_utc": _now()})
                _save("payment_reversal_period_locks", locks)
                st.rerun()
        for item in reversed(locks[-50:]):
            st.write(f"**{item.get('period')} · {'Activo' if item.get('active', True) else 'Liberado'}** — {item.get('responsible')}: {item.get('reason')}")

    with cases_tab:
        with st.form("payment_reversal_case_form", clear_on_submit=True):
            case_type = st.selectbox("Tipo", ("Diferencia con Caja", "Cliente reclama", "Proveedor reclama", "Doble reverso", "Falta evidencia", "Otro"))
            responsible = st.text_input("Responsable")
            description = st.text_area("Descripción", max_chars=700)
            submitted = st.form_submit_button("Abrir caso", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip() or not description.strip():
                st.error("Responsable y descripción son obligatorios.")
            else:
                cases.append({"case_id": f"PRK-{uuid4().hex[:8].upper()}", "case_type": case_type, "period": period, "responsible": responsible.strip(), "description": description.strip(), "status": "Abierto", "created_at_utc": _now()})
                _save("payment_reversal_support_cases", cases)
                st.rerun()
        for item in reversed(cases[-100:]):
            with st.container(border=True):
                st.markdown(f"**{item.get('case_id')} · {item.get('case_type')} · {item.get('status')}**")
                st.caption(f"{item.get('period')} · {item.get('responsible')}")
                st.write(item.get("description", ""))
                if item.get("status") != "Cerrado" and st.button("Cerrar caso", key=f"close_payment_reversal_case_{item.get('case_id')}", use_container_width=True):
                    changed = []
                    for case in cases:
                        current = dict(case)
                        if current.get("case_id") == item.get("case_id"):
                            current["status"] = "Cerrado"
                            current["closed_at_utc"] = _now()
                        changed.append(current)
                    _save("payment_reversal_support_cases", changed)
                    st.rerun()

    render_info_card("Reversos auditados", "El reverso ahora no solo se aplica: también se mide, se concilia con Caja y se puede bloquear por periodo.", "GOBIERNO")


app_shell.FUNCTIONAL_MODULES["Reversos de pagos"] = render_payment_reversals_governance
