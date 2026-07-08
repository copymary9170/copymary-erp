"""Gobierno avanzado de comisiones: escalas, simulación, recibos y bloqueos."""

from datetime import date, datetime, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup, team_commission_plus as base
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("commission_tiers", "Escalas de comisión"),
        ("commission_receipts", "Recibos de comisión"),
        ("commission_advances", "Anticipos de comisión"),
        ("commission_adjustments", "Ajustes de comisión"),
        ("commission_simulations", "Simulaciones de comisión"),
        ("commission_payment_locks", "Bloqueos de comisión"),
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


def _period() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def _member_name(member_id: str, members: list[dict]) -> str:
    return base._member_name(member_id, members)


def _period_value(member_id: str, assignments: list[dict], sales: list[dict], period: str) -> tuple[int, float, float]:
    return base._assignment_period_value(member_id, assignments, sales, period)


def _tier_rate(member_id: str, sales_total: float, period: str, tiers: list[dict]) -> float | None:
    valid = [
        row for row in tiers
        if row.get("period") == period and row.get("active", True)
        and str(row.get("member_id", "")) in {"", member_id}
        and sales_total >= _num(row.get("minimum_sales"))
    ]
    if not valid:
        return None
    return _num(max(valid, key=lambda row: _num(row.get("minimum_sales"))).get("commission_percent"))


def _locked(member_id: str, period: str, locks: list[dict]) -> bool:
    return any(row.get("member_id") == member_id and row.get("period") == period and row.get("active", True) for row in locks)


def _deductions(member_id: str, period: str, advances: list[dict], adjustments: list[dict]) -> tuple[float, float]:
    advance = sum(_num(row.get("amount")) for row in advances if row.get("member_id") == member_id and row.get("period") == period and row.get("status") != "Anulado")
    adjustment = sum(_num(row.get("amount")) for row in adjustments if row.get("member_id") == member_id and row.get("period") == period and row.get("status") != "Anulado")
    return advance, adjustment


def _period_payments(member_id: str, period: str, payments: list[dict]) -> float:
    return sum(_num(row.get("amount")) for row in payments if row.get("member_id") == member_id and str(row.get("payment_date", ""))[:7] == period and not row.get("reversed"))


def _balances(members: list[dict], assignments: list[dict], sales: list[dict], payments: list[dict], tiers: list[dict], advances: list[dict], adjustments: list[dict], period: str) -> list[dict]:
    rows = []
    for member in [row for row in members if row.get("active", True)]:
        member_id = str(member.get("member_id", ""))
        count, sales_total, base_commission = _period_value(member_id, assignments, sales, period)
        rate = _tier_rate(member_id, sales_total, period, tiers)
        commission = sales_total * rate / 100.0 if rate is not None else base_commission
        advance, adjustment = _deductions(member_id, period, advances, adjustments)
        paid = _period_payments(member_id, period, payments)
        rows.append({
            "member_id": member_id,
            "name": str(member.get("name", "Colaborador")),
            "sales_count": count,
            "sales_total": sales_total,
            "commission": commission,
            "rate_label": f"Escala {rate}%" if rate is not None else "Regla base",
            "advance": advance,
            "adjustment": adjustment,
            "paid": paid,
            "net": max(commission - advance - adjustment - paid, 0.0),
        })
    return rows


def _export_receipts(receipts: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Recibo", "Periodo", "Colaborador", "Ventas", "Comisión", "Deducciones", "Pagado", "Neto", "Estado"])
    for row in receipts:
        writer.writerow([row.get("receipt_id", ""), row.get("period", ""), row.get("member_name", ""), row.get("sales_total", 0), row.get("commission", 0), row.get("deductions", 0), row.get("paid", 0), row.get("net", 0), row.get("status", "")])
    return buffer.getvalue().encode("utf-8-sig")


def render_team_commission_governance() -> None:
    render_page_header("Equipo y comisiones", "Escalas, simulador, anticipos, ajustes, recibos y bloqueo de doble pago.")
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_team_commission_plus()
    finally:
        base.render_page_header = original_header

    members = _rows("team_members")
    assignments = _rows("commission_assignments")
    sales = _rows("sales_registry")
    payments = _rows("team_payments")
    tiers = _rows("commission_tiers")
    receipts = _rows("commission_receipts")
    advances = _rows("commission_advances")
    adjustments = _rows("commission_adjustments")
    simulations = _rows("commission_simulations")
    locks = _rows("commission_payment_locks")
    period = _period()
    balances = _balances(members, assignments, sales, payments, tiers, advances, adjustments, period)

    st.divider()
    st.markdown("### Gobierno avanzado de comisiones")
    cols = st.columns(5)
    cols[0].metric("Neto pendiente", format_money(sum(row["net"] for row in balances), get_currency()))
    cols[1].metric("Anticipos", format_money(sum(row["advance"] for row in balances), get_currency()))
    cols[2].metric("Ajustes", format_money(sum(row["adjustment"] for row in balances), get_currency()))
    cols[3].metric("Recibos", str(len(receipts)))
    cols[4].metric("Bloqueos", str(sum(1 for row in balances if _locked(row["member_id"], period, locks))))

    tier_tab, adjust_tab, sim_tab, receipt_tab = st.tabs(("Escalas", "Anticipos/Ajustes", "Simulador", "Recibos"))

    with tier_tab:
        active = [member for member in members if member.get("active", True)]
        member_labels = [f"{m.get('name')} · {m.get('member_id')}" for m in active]
        with st.form("commission_tier_form", clear_on_submit=True):
            apply_to = st.selectbox("Aplicar a", ("General", *member_labels))
            target_period = st.text_input("Periodo", value=period)
            minimum_sales = st.number_input("Ventas mínimas", min_value=0.0, value=0.0, step=10.0)
            commission_percent = st.number_input("Comisión %", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
            responsible = st.text_input("Responsable")
            submitted = st.form_submit_button("Guardar escala", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip():
                st.error("Indica responsable.")
            else:
                tiers.append({"tier_id": f"TIR-{uuid4().hex[:8].upper()}", "member_id": "" if apply_to == "General" else apply_to.split(" · ")[-1], "period": target_period.strip() or period, "minimum_sales": float(minimum_sales), "commission_percent": float(commission_percent), "responsible": responsible.strip(), "active": True, "created_at_utc": _now()})
                _save("commission_tiers", tiers)
                st.rerun()
        for row in reversed(tiers[-50:]):
            st.write(f"**{row.get('period')} · {row.get('member_id') or 'General'}** — desde {format_money(_num(row.get('minimum_sales')), get_currency())}: {row.get('commission_percent')}%")

    with adjust_tab:
        active = [member for member in members if member.get("active", True)]
        if not active:
            st.info("No hay colaboradores activos.")
        else:
            options = {f"{m.get('name')} · {m.get('member_id')}": m for m in active}
            with st.form("commission_adjustment_form", clear_on_submit=True):
                selected = st.selectbox("Colaborador", tuple(options.keys()))
                kind = st.selectbox("Tipo", ("Anticipo", "Ajuste / penalización"))
                amount = st.number_input("Monto", min_value=0.01, value=1.0, step=1.0)
                reason = st.text_area("Motivo", max_chars=400)
                submitted = st.form_submit_button("Guardar", type="primary", use_container_width=True)
            if submitted:
                if not reason.strip():
                    st.error("Indica motivo.")
                else:
                    member_id = str(options[selected].get("member_id", ""))
                    row = {"member_id": member_id, "period": period, "amount": float(amount), "reason": reason.strip(), "status": "Activo", "created_at_utc": _now()}
                    if kind == "Anticipo":
                        advances.append({"advance_id": f"ADV-{uuid4().hex[:8].upper()}", **row})
                        _save("commission_advances", advances)
                    else:
                        adjustments.append({"adjustment_id": f"ADJ-{uuid4().hex[:8].upper()}", **row})
                        _save("commission_adjustments", adjustments)
                    st.rerun()

    with sim_tab:
        with st.form("commission_simulation_form", clear_on_submit=True):
            projected_sales = st.number_input("Ventas proyectadas", min_value=0.0, value=100.0, step=10.0)
            rate = st.number_input("Comisión %", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
            deductions = st.number_input("Deducciones", min_value=0.0, value=0.0, step=1.0)
            note = st.text_input("Nota")
            submitted = st.form_submit_button("Guardar simulación", type="primary", use_container_width=True)
        if submitted:
            gross = float(projected_sales) * float(rate) / 100.0
            simulations.append({"simulation_id": f"SIM-{uuid4().hex[:8].upper()}", "period": period, "projected_sales": float(projected_sales), "rate": float(rate), "gross": gross, "deductions": float(deductions), "net": max(gross - float(deductions), 0.0), "note": note.strip(), "created_at_utc": _now()})
            _save("commission_simulations", simulations)
            st.rerun()
        for row in reversed(simulations[-30:]):
            st.write(f"**{row.get('simulation_id')}** · neto {format_money(_num(row.get('net')), get_currency())} · {row.get('note', '')}")

    with receipt_tab:
        st.download_button("Descargar recibos CSV", data=_export_receipts(receipts), file_name=f"recibos_comision_{period}.csv", mime="text/csv", use_container_width=True, disabled=not receipts)
        for row in balances:
            is_locked = _locked(row["member_id"], period, locks)
            with st.container(border=True):
                c = st.columns([3, 1, 1, 1])
                c[0].markdown(f"**{row['name']} · {period}**")
                c[0].caption(row["rate_label"])
                c[1].metric("Comisión", format_money(row["commission"], get_currency()))
                c[2].metric("Deducciones", format_money(row["advance"] + row["adjustment"], get_currency()))
                c[3].metric("Neto", format_money(row["net"], get_currency()))
                if st.button("Emitir recibo y bloquear", key=f"receipt_{row['member_id']}_{period}", use_container_width=True, disabled=is_locked or row["net"] <= 0):
                    receipt_id = f"RCP-{uuid4().hex[:8].upper()}"
                    receipts.append({"receipt_id": receipt_id, "period": period, "member_id": row["member_id"], "member_name": row["name"], "sales_total": row["sales_total"], "commission": row["commission"], "deductions": row["advance"] + row["adjustment"], "paid": row["paid"], "net": row["net"], "status": "Emitido", "created_at_utc": _now()})
                    locks.append({"lock_id": f"LCK-{uuid4().hex[:8].upper()}", "member_id": row["member_id"], "period": period, "receipt_id": receipt_id, "active": True, "created_at_utc": _now()})
                    _save("commission_receipts", receipts)
                    _save("commission_payment_locks", locks)
                    st.rerun()

    render_info_card("Pago protegido", "Las comisiones ahora se simulan, ajustan, emiten como recibo y se bloquean para evitar doble pago.", "GOBIERNO DE COMISIONES")


app_shell.FUNCTIONAL_MODULES["Equipo y comisiones"] = render_team_commission_governance
