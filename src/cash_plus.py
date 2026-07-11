"""Caja avanzada con apertura, arqueo, cierre, diferencias y trazabilidad."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("cash_sessions", "Sesiones de caja"),
        ("cash_counts", "Arqueos de caja"),
        ("cash_adjustments", "Ajustes de caja"),
        ("cash_audit_log", "Auditoría de caja"),
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
    for session in reversed(sessions):
        if session.get("status") == "Abierta":
            return dict(session)
    return None


def _session_movements(session: dict | None, movements: list[dict]) -> list[dict]:
    if not session:
        return []
    start = _dt(session.get("opened_at_utc"))
    end = _dt(session.get("closed_at_utc")) or datetime.now()
    result = []
    for movement in movements:
        created = _dt(movement.get("created_at_utc"))
        if created and start and start <= created <= end:
            result.append(dict(movement))
    return result


def _balance(movements: list[dict]) -> float:
    income = sum(_num(row.get("amount")) for row in movements if row.get("movement_type") == "Ingreso")
    expense = sum(_num(row.get("amount")) for row in movements if row.get("movement_type") == "Egreso")
    return income - expense


def _method_summary(movements: list[dict]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = defaultdict(lambda: {"income": 0.0, "expense": 0.0, "balance": 0.0})
    for movement in movements:
        method = str(movement.get("payment_method", "Otro"))
        amount = _num(movement.get("amount"))
        if movement.get("movement_type") == "Ingreso":
            output[method]["income"] += amount
            output[method]["balance"] += amount
        else:
            output[method]["expense"] += amount
            output[method]["balance"] -= amount
    return output


def _audit(action: str, note: str, responsible: str = "") -> None:
    rows = _rows("cash_audit_log")
    rows.append({
        "audit_id": f"CAU-{uuid4().hex[:8].upper()}",
        "action": action,
        "note": note.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("cash_audit_log", rows)


def _append_movement(movement_type: str, category: str, amount: float, method: str, reference: str, notes: str, responsible: str, session_id: str = "") -> None:
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


def _close_session(session_id: str, expected: float, counted: float, responsible: str, note: str) -> None:
    sessions = _rows("cash_sessions")
    changed = []
    for session in sessions:
        row = dict(session)
        if str(row.get("session_id", "")) == session_id:
            row["status"] = "Cerrada"
            row["expected_cash"] = float(expected)
            row["counted_cash"] = float(counted)
            row["difference"] = float(counted) - float(expected)
            row["closed_by"] = responsible.strip() or "Sin asignar"
            row["closing_note"] = note.strip()
            row["closed_at_utc"] = _now()
        changed.append(row)
    _save("cash_sessions", changed)
    _audit("Cierre de caja", f"Esperado {expected:,.2f}; contado {counted:,.2f}; diferencia {counted - expected:+,.2f}. {note}", responsible)


def _export(movements: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Fecha", "Tipo", "Categoría", "Monto", "Método", "Referencia", "Responsable", "Estado", "Notas"])
    for row in movements:
        writer.writerow([
            row.get("movement_id", ""), row.get("created_at_utc", ""), row.get("movement_type", ""), row.get("category", ""),
            row.get("amount", 0), row.get("payment_method", ""), row.get("reference", ""), row.get("responsible", ""),
            row.get("status", "Aplicado"), row.get("notes", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_cash_plus() -> None:
    render_page_header(
        "Caja",
        "Controla apertura, movimientos, arqueo, diferencias, cierre y auditoría de caja.",
    )

    movements = _rows("cash_movements")
    sessions = _rows("cash_sessions")
    counts = _rows("cash_counts")
    audit = _rows("cash_audit_log")
    active = _active_session(sessions)
    session_movements = _session_movements(active, movements) if active else movements
    total_income = sum(_num(row.get("amount")) for row in session_movements if row.get("movement_type") == "Ingreso")
    total_expense = sum(_num(row.get("amount")) for row in session_movements if row.get("movement_type") == "Egreso")
    opening = _num(active.get("opening_amount")) if active else 0.0
    expected = opening + total_income - total_expense

    metrics = st.columns(5)
    metrics[0].metric("Estado", "Abierta" if active else "Sin apertura")
    metrics[1].metric("Fondo inicial", format_money(opening, get_currency()))
    metrics[2].metric("Ingresos", format_money(total_income, get_currency()))
    metrics[3].metric("Egresos", format_money(total_expense, get_currency()))
    metrics[4].metric("Saldo esperado", format_money(expected, get_currency()))

    if not active:
        st.warning("No hay caja abierta. Puedes registrar una apertura antes de operar.")

    open_tab, movement_tab, count_tab, close_tab, history_tab, audit_tab = st.tabs(
        ("Apertura", "Movimientos", "Arqueo", "Cierre", "Historial", "Auditoría")
    )

    with open_tab:
        if active:
            st.success(f"Caja abierta: {active.get('session_id', '')} · {active.get('opened_by', 'Sin asignar')}")
            st.caption(str(active.get("opening_note", "")))
        else:
            with st.form("cash_open_form", clear_on_submit=True):
                cols = st.columns(4)
                opening_amount = cols[0].number_input("Fondo inicial", min_value=0.0, value=0.0, step=1.0)
                opened_by = cols[1].text_input("Abierta por")
                location = cols[2].text_input("Punto de caja", value="Principal")
                currency = cols[3].selectbox("Moneda", (get_currency(), "USD", "VES", "EUR"))
                note = st.text_area("Observación", max_chars=400)
                submitted = st.form_submit_button("Abrir caja", type="primary", use_container_width=True)
            if submitted:
                if not opened_by.strip():
                    st.error("Indica quién abre la caja.")
                else:
                    session_id = f"CSH-{uuid4().hex[:8].upper()}"
                    sessions.append({
                        "session_id": session_id,
                        "opened_at_utc": _now(),
                        "opened_by": opened_by.strip(),
                        "location": location.strip() or "Principal",
                        "currency": currency,
                        "opening_amount": float(opening_amount),
                        "opening_note": note.strip(),
                        "status": "Abierta",
                    })
                    _save("cash_sessions", sessions)
                    _audit("Apertura de caja", f"Fondo inicial {opening_amount:,.2f}. {note}", opened_by)
                    st.rerun()

    with movement_tab:
        with st.form("cash_plus_movement_form", clear_on_submit=True):
            cols = st.columns(5)
            movement_type = cols[0].selectbox("Movimiento", ("Ingreso", "Egreso"))
            category = cols[1].selectbox("Categoría", ("Venta", "Compra", "Servicio", "Transporte", "Retiro", "Cambio", "Ajuste", "Otro"))
            amount = cols[2].number_input("Monto", min_value=0.01, value=1.0, step=1.0)
            payment_method = cols[3].selectbox("Método", ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Punto", "Otro"))
            responsible = cols[4].text_input("Responsable")
            reference = st.text_input("Referencia", placeholder="Venta, factura, pago móvil, transferencia")
            notes = st.text_area("Concepto o nota", max_chars=400)
            confirmed = st.checkbox("Confirmo el movimiento")
            submitted = st.form_submit_button("Registrar movimiento", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip() or not notes.strip() or not confirmed:
                st.error("Responsable, concepto y confirmación son obligatorios.")
            elif not active:
                st.error("Debes abrir caja antes de registrar movimientos manuales.")
            else:
                _append_movement(movement_type, category, float(amount), payment_method, reference, notes, responsible, str(active.get("session_id", "")))
                st.rerun()

        st.markdown("#### Resumen por método")
        for method, values in _method_summary(session_movements).items():
            with st.container(border=True):
                cols = st.columns(4)
                cols[0].markdown(f"**{method}**")
                cols[1].metric("Ingresos", format_money(values["income"], get_currency()))
                cols[2].metric("Egresos", format_money(values["expense"], get_currency()))
                cols[3].metric("Neto", format_money(values["balance"], get_currency()))

    with count_tab:
        if not active:
            st.info("Abre caja para registrar arqueos.")
        else:
            method_balances = _method_summary(session_movements)
            with st.form("cash_count_form", clear_on_submit=True):
                st.caption("Registra el efectivo contado y otros métodos para detectar diferencias.")
                counted_cash = st.number_input("Efectivo contado", min_value=0.0, value=max(method_balances.get("Efectivo", {}).get("balance", 0.0) + opening, 0.0), step=1.0)
                counted_mobile = st.number_input("Pago móvil / transferencias verificadas", min_value=0.0, value=0.0, step=1.0)
                responsible = st.text_input("Responsable del arqueo")
                note = st.text_area("Observación", max_chars=400)
                submitted = st.form_submit_button("Guardar arqueo", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip():
                    st.error("Indica responsable del arqueo.")
                else:
                    expected_cash = opening + method_balances.get("Efectivo", {}).get("balance", 0.0)
                    counts.append({
                        "count_id": f"CNT-{uuid4().hex[:8].upper()}",
                        "session_id": str(active.get("session_id", "")),
                        "expected_cash": expected_cash,
                        "counted_cash": float(counted_cash),
                        "cash_difference": float(counted_cash) - expected_cash,
                        "verified_digital": float(counted_mobile),
                        "responsible": responsible.strip(),
                        "note": note.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("cash_counts", counts)
                    _audit("Arqueo", f"Diferencia efectivo {float(counted_cash) - expected_cash:+,.2f}. {note}", responsible)
                    st.rerun()

        for count in reversed(counts[-20:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**Arqueo {count.get('count_id', '')}**")
                cols[0].caption(f"{count.get('created_at_utc', '')} · {count.get('responsible', '')}")
                cols[1].metric("Esperado", format_money(_num(count.get("expected_cash")), get_currency()))
                cols[2].metric("Contado", format_money(_num(count.get("counted_cash")), get_currency()))
                cols[3].metric("Diferencia", format_money(_num(count.get("cash_difference")), get_currency()))

    with close_tab:
        if not active:
            st.info("No hay caja abierta para cerrar.")
        else:
            with st.form("cash_close_form"):
                counted_cash = st.number_input("Total contado para cierre", min_value=0.0, value=max(expected, 0.0), step=1.0)
                responsible = st.text_input("Cerrada por")
                note = st.text_area("Nota de cierre", max_chars=500)
                confirmed = st.checkbox("Confirmo que deseo cerrar la caja")
                submitted = st.form_submit_button("Cerrar caja", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not confirmed:
                    st.error("Responsable y confirmación son obligatorios.")
                else:
                    _close_session(str(active.get("session_id", "")), expected, float(counted_cash), responsible, note)
                    st.rerun()

    with history_tab:
        filters = st.columns(4)
        period = filters[0].selectbox("Periodo", ("Todo", "Hoy", "7 días", "30 días"))
        type_filter = filters[1].selectbox("Tipo", ("Todos", "Ingreso", "Egreso"))
        method_filter = filters[2].selectbox("Método", ("Todos", *sorted({str(row.get("payment_method", "Otro")) for row in movements})))
        query = filters[3].text_input("Buscar").strip().casefold()
        days = {"Hoy": 0, "7 días": 7, "30 días": 30}.get(period)
        cutoff = datetime.combine(date.today(), datetime.min.time()) if days == 0 else datetime.now() - timedelta(days=days) if days else None
        visible = []
        for row in movements:
            created = _dt(row.get("created_at_utc"))
            text = " ".join(str(row.get(field, "")) for field in ("category", "notes", "reference", "responsible")).casefold()
            if cutoff and (not created or created < cutoff):
                continue
            if type_filter != "Todos" and row.get("movement_type") != type_filter:
                continue
            if method_filter != "Todos" and row.get("payment_method") != method_filter:
                continue
            if query and query not in text:
                continue
            visible.append(row)
        st.download_button("Descargar movimientos CSV", data=_export(visible), file_name=f"caja_movimientos_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not visible)
        for row in reversed(visible[-150:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{row.get('movement_type', '')}: {row.get('category', '')}**")
                cols[0].caption(f"{row.get('created_at_utc', '')} · {row.get('payment_method', '')} · {row.get('responsible', 'Sin asignar')}")
                cols[1].metric("Monto", format_money(_num(row.get("amount")), get_currency()))
                cols[2].metric("Estado", str(row.get("status", "Aplicado")))
                st.caption(str(row.get("notes", "")))

    with audit_tab:
        st.markdown("#### Sesiones cerradas")
        for session in reversed([row for row in sessions if row.get("status") == "Cerrada"][-50:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{session.get('session_id', '')} · {session.get('location', '')}**")
                cols[0].caption(f"{session.get('opened_at_utc', '')} → {session.get('closed_at_utc', '')}")
                cols[1].metric("Esperado", format_money(_num(session.get("expected_cash")), get_currency()))
                cols[2].metric("Contado", format_money(_num(session.get("counted_cash")), get_currency()))
                cols[3].metric("Diferencia", format_money(_num(session.get("difference")), get_currency()))
        st.markdown("#### Auditoría")
        if not audit:
            st.info("No hay auditoría de caja.")
        for entry in reversed(audit[-100:]):
            st.write(f"**{entry.get('action', '')}** · {entry.get('responsible', '')} · {entry.get('created_at_utc', '')} — {entry.get('note', '')}")

    render_info_card(
        "Caja controlada",
        "Las aperturas, arqueos, cierres y movimientos quedan registrados para evitar descuadres sin explicación.",
        "CONTROL FINANCIERO",
    )


app_shell.FUNCTIONAL_MODULES["Caja"] = render_cash_plus
