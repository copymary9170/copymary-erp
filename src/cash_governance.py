"""Gobierno de caja: conciliación, depósitos, denominaciones y diferencias."""

from collections import defaultdict
from datetime import date, datetime
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, cash_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("cash_bank_deposits", "Depósitos bancarios desde caja"),
        ("cash_discrepancy_cases", "Casos de diferencias de caja"),
        ("cash_denominations", "Conteo por denominación de caja"),
        ("cash_close_checklists", "Listas de verificación de cierre de caja"),
        ("cash_reconciliations", "Conciliaciones de caja"),
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


def _active_session(sessions: list[dict]) -> dict | None:
    return base._active_session(sessions)


def _session_movements(session: dict | None, movements: list[dict]) -> list[dict]:
    return base._session_movements(session, movements)


def _method_summary(movements: list[dict]) -> dict[str, dict[str, float]]:
    return base._method_summary(movements)


def _audit(action: str, note: str, responsible: str = "") -> None:
    base._audit(action, note, responsible)


def _cash_expected(active: dict | None, movements: list[dict]) -> float:
    if not active:
        return 0.0
    opening = _num(active.get("opening_amount"))
    cash_movements = [row for row in movements if row.get("payment_method") == "Efectivo"]
    income = sum(_num(row.get("amount")) for row in cash_movements if row.get("movement_type") == "Ingreso")
    expense = sum(_num(row.get("amount")) for row in cash_movements if row.get("movement_type") == "Egreso")
    return opening + income - expense


def _append_cash_movement(movement_type: str, category: str, amount: float, method: str, reference: str, notes: str, responsible: str, session_id: str) -> None:
    movements = _rows("cash_movements")
    movements.append({
        "movement_id": uuid4().hex[:10],
        "created_at_utc": _now(),
        "movement_type": movement_type,
        "category": category,
        "amount": float(amount),
        "payment_method": method,
        "reference": reference.strip(),
        "notes": notes.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "cash_session_id": session_id,
        "status": "Aplicado",
        "reversed": False,
    })
    _save("cash_movements", movements)
    _audit(movement_type, f"{category}: {amount:,.2f}. {notes}", responsible)


def _export_cases(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Caso", "Sesión", "Tipo", "Diferencia", "Estado", "Responsable", "Motivo", "Fecha"])
    for row in rows:
        writer.writerow([
            row.get("case_id", ""), row.get("session_id", ""), row.get("case_type", ""), row.get("difference", 0),
            row.get("status", ""), row.get("responsible", ""), row.get("reason", ""), row.get("created_at_utc", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def _export_deposits(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Depósito", "Sesión", "Banco", "Monto", "Estado", "Responsable", "Referencia", "Fecha"])
    for row in rows:
        writer.writerow([
            row.get("deposit_id", ""), row.get("session_id", ""), row.get("bank", ""), row.get("amount", 0),
            row.get("status", ""), row.get("responsible", ""), row.get("reference", ""), row.get("created_at_utc", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_cash_governance() -> None:
    render_page_header(
        "Caja",
        "Añade depósitos, denominaciones, conciliación por método y seguimiento de diferencias.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_cash_plus()
    finally:
        base.render_page_header = original_header

    movements = _rows("cash_movements")
    sessions = _rows("cash_sessions")
    deposits = _rows("cash_bank_deposits")
    cases = _rows("cash_discrepancy_cases")
    denominations = _rows("cash_denominations")
    checklists = _rows("cash_close_checklists")
    reconciliations = _rows("cash_reconciliations")
    active = _active_session(sessions)
    active_movements = _session_movements(active, movements) if active else []
    method_summary = _method_summary(active_movements)
    expected_cash = _cash_expected(active, active_movements)
    open_cases = [row for row in cases if row.get("status") in {"Abierto", "En revisión"}]
    pending_deposits = [row for row in deposits if row.get("status") == "Pendiente"]
    unreconciled = [row for row in reconciliations if row.get("status") != "Conciliado"]

    st.divider()
    st.markdown("### Control gerencial de caja")
    metrics = st.columns(5)
    metrics[0].metric("Efectivo esperado", format_money(expected_cash, get_currency()))
    metrics[1].metric("Depósitos pendientes", str(len(pending_deposits)))
    metrics[2].metric("Diferencias abiertas", str(len(open_cases)))
    metrics[3].metric("Conciliaciones abiertas", str(len(unreconciled)))
    metrics[4].metric("Cierres verificados", str(len(checklists)))

    if open_cases:
        st.error(f"Hay {len(open_cases)} diferencia(s) de caja sin resolver.")
    if pending_deposits:
        st.warning(f"Hay {len(pending_deposits)} depósito(s) pendiente(s) de confirmación.")

    deposit_tab, denomination_tab, reconcile_tab, cases_tab, checklist_tab = st.tabs(
        ("Depósitos", "Denominaciones", "Conciliación", "Diferencias", "Checklist de cierre")
    )

    with deposit_tab:
        if not active:
            st.info("Abre caja para registrar depósitos desde efectivo.")
        else:
            with st.form("cash_bank_deposit_form", clear_on_submit=True):
                cols = st.columns(4)
                amount = cols[0].number_input("Monto a depositar", min_value=0.01, value=1.0, step=1.0)
                bank = cols[1].text_input("Banco o destino")
                responsible = cols[2].text_input("Responsable")
                reference = cols[3].text_input("Referencia")
                note = st.text_area("Observación", max_chars=400)
                confirmed = st.checkbox("Confirmo salida de efectivo para depósito")
                submitted = st.form_submit_button("Registrar depósito pendiente", type="primary", use_container_width=True)
            if submitted:
                if not bank.strip() or not responsible.strip() or not confirmed:
                    st.error("Banco, responsable y confirmación son obligatorios.")
                elif float(amount) > expected_cash:
                    st.error("El depósito supera el efectivo esperado en caja.")
                else:
                    deposit_id = f"DEP-{uuid4().hex[:8].upper()}"
                    deposits.append({
                        "deposit_id": deposit_id,
                        "session_id": str(active.get("session_id", "")),
                        "amount": float(amount),
                        "bank": bank.strip(),
                        "reference": reference.strip(),
                        "responsible": responsible.strip(),
                        "note": note.strip(),
                        "status": "Pendiente",
                        "created_at_utc": _now(),
                    })
                    _save("cash_bank_deposits", deposits)
                    _append_cash_movement("Egreso", "Depósito bancario", float(amount), "Efectivo", deposit_id, note or f"Depósito a {bank}", responsible, str(active.get("session_id", "")))
                    st.rerun()

        st.download_button("Descargar depósitos CSV", data=_export_deposits(deposits), file_name=f"depositos_caja_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not deposits)
        for deposit in reversed(deposits[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{deposit.get('deposit_id', '')} · {deposit.get('bank', '')}**")
                cols[0].caption(f"{deposit.get('responsible', '')} · {deposit.get('reference', '')} · {deposit.get('created_at_utc', '')}")
                cols[1].metric("Monto", format_money(_num(deposit.get("amount")), get_currency()))
                cols[2].metric("Estado", str(deposit.get("status", "")))
                if deposit.get("status") == "Pendiente" and st.button("Confirmar depósito", key=f"confirm_deposit_{deposit.get('deposit_id')}", use_container_width=True):
                    changed = []
                    for row in deposits:
                        current = dict(row)
                        if current.get("deposit_id") == deposit.get("deposit_id"):
                            current["status"] = "Confirmado"
                            current["confirmed_at_utc"] = _now()
                        changed.append(current)
                    _save("cash_bank_deposits", changed)
                    _audit("Depósito confirmado", str(deposit.get("deposit_id", "")), str(deposit.get("responsible", "")))
                    st.rerun()

    with denomination_tab:
        if not active:
            st.info("Abre caja para contar denominaciones.")
        else:
            st.caption("Cuenta billetes/monedas para comparar el efectivo real contra lo esperado.")
            with st.form("cash_denomination_form", clear_on_submit=True):
                denoms = [100, 50, 20, 10, 5, 1, 0.5, 0.25, 0.1, 0.05]
                values = {}
                cols = st.columns(5)
                for index, denom in enumerate(denoms):
                    values[str(denom)] = cols[index % 5].number_input(f"{denom:g}", min_value=0, value=0, step=1, key=f"denom_{denom}")
                responsible = st.text_input("Responsable del conteo")
                note = st.text_input("Nota")
                submitted = st.form_submit_button("Guardar conteo por denominación", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip():
                    st.error("Indica responsable del conteo.")
                else:
                    total = sum(float(denom) * int(count) for denom, count in values.items())
                    denominations.append({
                        "denomination_id": f"DEN-{uuid4().hex[:8].upper()}",
                        "session_id": str(active.get("session_id", "")),
                        "values": values,
                        "total": total,
                        "expected_cash": expected_cash,
                        "difference": total - expected_cash,
                        "responsible": responsible.strip(),
                        "note": note.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("cash_denominations", denominations)
                    _audit("Conteo por denominación", f"Total {total:,.2f}; diferencia {total - expected_cash:+,.2f}", responsible)
                    st.rerun()
        for row in reversed(denominations[-30:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**Conteo {row.get('denomination_id', '')}**")
                cols[0].caption(f"{row.get('responsible', '')} · {row.get('created_at_utc', '')}")
                cols[1].metric("Total", format_money(_num(row.get("total")), get_currency()))
                cols[2].metric("Diferencia", format_money(_num(row.get("difference")), get_currency()))

    with reconcile_tab:
        st.caption("Compara montos esperados por método contra los montos verificados por comprobantes, bancos o punto.")
        if not active:
            st.info("Abre caja para conciliar la sesión activa.")
        else:
            with st.form("cash_reconciliation_form", clear_on_submit=True):
                method = st.selectbox("Método", tuple(sorted(method_summary.keys())) if method_summary else ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Punto", "Otro"))
                expected_method = method_summary.get(method, {}).get("balance", 0.0)
                verified = st.number_input("Monto verificado", min_value=0.0, value=max(float(expected_method), 0.0), step=1.0)
                responsible = st.text_input("Responsable")
                reference = st.text_input("Referencia de conciliación")
                note = st.text_area("Observación", max_chars=400)
                submitted = st.form_submit_button("Guardar conciliación", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip():
                    st.error("Indica responsable.")
                else:
                    difference = float(verified) - float(expected_method)
                    reconciliations.append({
                        "reconciliation_id": f"REC-{uuid4().hex[:8].upper()}",
                        "session_id": str(active.get("session_id", "")),
                        "method": method,
                        "expected": float(expected_method),
                        "verified": float(verified),
                        "difference": difference,
                        "reference": reference.strip(),
                        "responsible": responsible.strip(),
                        "note": note.strip(),
                        "status": "Conciliado" if abs(difference) < 0.01 else "Diferencia",
                        "created_at_utc": _now(),
                    })
                    _save("cash_reconciliations", reconciliations)
                    if abs(difference) >= 0.01:
                        cases.append({
                            "case_id": f"DIF-{uuid4().hex[:8].upper()}",
                            "session_id": str(active.get("session_id", "")),
                            "case_type": f"Diferencia en {method}",
                            "difference": difference,
                            "responsible": responsible.strip(),
                            "reason": note.strip(),
                            "status": "Abierto",
                            "created_at_utc": _now(),
                        })
                        _save("cash_discrepancy_cases", cases)
                    st.rerun()
        for row in reversed(reconciliations[-50:]):
            st.write(f"**{row.get('method', '')}** · esperado {format_money(_num(row.get('expected')), get_currency())} · verificado {format_money(_num(row.get('verified')), get_currency())} · {row.get('status', '')}")

    with cases_tab:
        st.download_button("Descargar diferencias CSV", data=_export_cases(cases), file_name=f"diferencias_caja_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not cases)
        if not cases:
            st.success("No hay casos de diferencia registrados.")
        for case in reversed(cases[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{case.get('case_id', '')} · {case.get('case_type', '')}**")
                cols[0].caption(f"{case.get('responsible', '')} · {case.get('created_at_utc', '')} · {case.get('reason', '')}")
                cols[1].metric("Diferencia", format_money(_num(case.get("difference")), get_currency()))
                cols[2].metric("Estado", str(case.get("status", "")))
                if case.get("status") != "Resuelto":
                    with st.form(f"resolve_case_{case.get('case_id')}"):
                        resolution = st.text_area("Resolución", max_chars=400, key=f"resolution_{case.get('case_id')}")
                        responsible = st.text_input("Responsable cierre", key=f"resolver_{case.get('case_id')}")
                        submitted = st.form_submit_button("Resolver diferencia", type="primary", use_container_width=True)
                    if submitted:
                        if not resolution.strip() or not responsible.strip():
                            st.error("Resolución y responsable son obligatorios.")
                        else:
                            changed = []
                            for row in cases:
                                current = dict(row)
                                if current.get("case_id") == case.get("case_id"):
                                    current["status"] = "Resuelto"
                                    current["resolution"] = resolution.strip()
                                    current["resolved_by"] = responsible.strip()
                                    current["resolved_at_utc"] = _now()
                                changed.append(current)
                            _save("cash_discrepancy_cases", changed)
                            _audit("Diferencia resuelta", str(case.get("case_id", "")), responsible)
                            st.rerun()

    with checklist_tab:
        if not active:
            st.info("Abre caja para usar checklist de cierre.")
        else:
            with st.form("cash_close_checklist_form", clear_on_submit=True):
                c1 = st.checkbox("Ventas pagadas revisadas")
                c2 = st.checkbox("Comprobantes digitales verificados")
                c3 = st.checkbox("Efectivo contado")
                c4 = st.checkbox("Depósitos pendientes revisados")
                c5 = st.checkbox("Diferencias explicadas")
                responsible = st.text_input("Responsable")
                note = st.text_input("Nota")
                submitted = st.form_submit_button("Guardar checklist", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip():
                    st.error("Indica responsable.")
                else:
                    completed = sum(bool(item) for item in (c1, c2, c3, c4, c5))
                    checklists.append({
                        "checklist_id": f"CHK-{uuid4().hex[:8].upper()}",
                        "session_id": str(active.get("session_id", "")),
                        "completed": completed,
                        "total": 5,
                        "ready_to_close": completed == 5,
                        "responsible": responsible.strip(),
                        "note": note.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("cash_close_checklists", checklists)
                    _audit("Checklist cierre", f"{completed}/5 puntos completados", responsible)
                    st.rerun()
        for item in reversed(checklists[-30:]):
            st.write(f"**{item.get('checklist_id', '')}** · {item.get('completed', 0)}/{item.get('total', 5)} · {'Listo para cerrar' if item.get('ready_to_close') else 'Incompleto'} · {item.get('responsible', '')}")

    render_info_card(
        "Caja supervisada",
        "Los depósitos, conciliaciones, denominaciones y diferencias quedan enlazados a la sesión de caja.",
        "GOBIERNO DE CAJA",
    )


app_shell.FUNCTIONAL_MODULES["Caja"] = render_cash_governance
