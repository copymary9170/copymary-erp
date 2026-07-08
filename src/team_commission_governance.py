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
        ("commission_penalties", "Ajustes y penalizaciones de comisión"),
        ("commission_simulations", "Simulaciones de comisión"),
        ("commission_payment_locks", "Bloqueos de doble pago de comisión"),
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


def _period_key(value: date | None = None) -> str:
    current = value or date.today()
    return f"{current.year:04d}-{current.month:02d}"


def _member_name(member_id: str, members: list[dict]) -> str:
    return base._member_name(member_id, members)


def _paid(member_id: str, payments: list[dict]) -> float:
    return base._paid(member_id, payments)


def _assignment_period_value(member_id: str, assignments: list[dict], sales: list[dict], period: str) -> tuple[int, float, float]:
    return base._assignment_period_value(member_id, assignments, sales, period)


def _tier_rate(member_id: str, sales_total: float, tiers: list[dict], period: str) -> float | None:
    candidates = [
        row for row in tiers
        if row.get("period") == period
        and row.get("active", True)
        and (str(row.get("member_id", "")) in {"", member_id})
        and sales_total >= _num(row.get("minimum_sales"))
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda row: _num(row.get("minimum_sales")))
    return _num(best.get("commission_percent"))


def _adjustments(member_id: str, period: str, advances: list[dict], penalties: list[dict]) -> tuple[float, float]:
    advance = sum(_num(row.get("amount")) for row in advances if row.get("period") == period and row.get("member_id") == member_id and row.get("status") != "Anulado")
    penalty = sum(_num(row.get("amount")) for row in penalties if row.get("period") == period and row.get("member_id") == member_id and row.get("status") != "Anulado")
    return advance, penalty


def _period_balance(member: dict, assignments: list[dict], sales: list[dict], payments: list[dict], tiers: list[dict], advances: list[dict], penalties: list[dict], period: str) -> dict:
    member_id = str(member.get("member_id", ""))
    count, sales_total, base_commission = _assignment_period_value(member_id, assignments, sales, period)
    tier_rate = _tier_rate(member_id, sales_total, tiers, period)
    if tier_rate is not None:
        commission = sales_total * tier_rate / 100.0
        source = f"Escala {tier_rate:,.2f}%"
    else:
        commission = base_commission
        source = "Regla base"
    advance, penalty = _adjustments(member_id, period, advances, penalties)
    paid = sum(_num(row.get("amount")) for row in payments if row.get("member_id") == member_id and str(row.get("payment_date", ""))[:7] == period and not row.get("reversed"))
    net = max(commission - advance - penalty - paid, 0.0)
    return {
        "member_id": member_id,
        "name": str(member.get("name", "Colaborador")),
        "sales_count": count,
        "sales_total": sales_total,
        "commission": commission,
        "commission_source": source,
        "advances": advance,
        "penalties": penalty,
        "paid_period": paid,
        "net_pending": net,
    }


def _is_locked(member_id: str, period: str, locks: list[dict]) -> bool:
    return any(row.get("member_id") == member_id and row.get("period") == period and row.get("active", True) for row in locks)


def _export_receipts(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Recibo", "Periodo", "Colaborador", "Ventas", "Comisión", "Anticipos", "Ajustes", "Pagado", "Neto", "Estado"])
    for row in rows:
        writer.writerow([
            row.get("receipt_id", ""), row.get("period", ""), row.get("member_name", ""), row.get("sales_total", 0),
            row.get("commission", 0), row.get("advances", 0), row.get("penalties", 0), row.get("paid_period", 0),
            row.get("net_pending", 0), row.get("status", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_team_commission_governance() -> None:
    render_page_header(
        "Equipo y comisiones",
        "Agrega escalas automáticas, anticipos, ajustes, simulador, recibos y bloqueo de doble pago.",
    )

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
    penalties = _rows("commission_penalties")
    simulations = _rows("commission_simulations")
    locks = _rows("commission_payment_locks")
    period = _period_key()
    active = [member for member in members if member.get("active", True)]
    balances = [_period_balance(member, assignments, sales, payments, tiers, advances, penalties, period) for member in active]
    locked_count = sum(1 for row in balances if _is_locked(row["member_id"], period, locks))

    st.divider()
    st.markdown("### Gobierno avanzado de comisiones")
    metrics = st.columns(5)
    metrics[0].metric("Comisión neta", format_money(sum(row["net_pending"] for row in balances), get_currency()))
    metrics[1].metric("Anticipos", format_money(sum(row["advances"] for row in balances), get_currency()))
    metrics[2].metric("Ajustes", format_money(sum(row["penalties"] for row in balances), get_currency()))
    metrics[3].metric("Recibos", str(len(receipts)))
    metrics[4].metric("Bloqueados", str(locked_count))

    if locked_count:
        st.warning("Hay colaboradores con comisión bloqueada para evitar doble pago del periodo.")

    tier_tab, adjustment_tab, simulation_tab, receipt_tab, lock_tab = st.tabs(("Escalas", "Anticipos y ajustes", "Simulador", "Recibos", "Bloqueos"))

    with tier_tab:
        with st.form("commission_tier_form", clear_on_submit=True):
            cols = st.columns(5)
            selected_member = cols[0].selectbox("Aplicar a", ("General", *[f"{m.get('name')} · {m.get('member_id')}" for m in active]))
            target_period = cols[1].text_input("Periodo", value=period)
            minimum_sales = cols[2].number_input("Ventas mínimas", min_value=0.0, value=0.0, step=10.0)
            commission_percent = cols[3].number_input("Comisión %", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
            responsible = cols[4].text_input("Responsable")
            submitted = st.form_submit_button("Guardar escala", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip():
                st.error("Indica responsable.")
            else:
                member_id = "" if selected_member == "General" else selected_member.split(" · ")[-1]
                tiers.append({
                    "tier_id": f"TIR-{uuid4().hex[:8].upper()}",
                    "member_id": member_id,
                    "period": target_period.strip() or period,
                    "minimum_sales": float(minimum_sales),
                    "commission_percent": float(commission_percent),
                    "responsible": responsible.strip(),
                    "active": True,
                    "created_at_utc": _now(),
                })
                _save("commission_tiers", tiers)
                st.rerun()
        for row in reversed(tiers[-100:]):
            st.write(f"**{row.get('period', '')} · {row.get('member_id') or 'General'}** — desde {format_money(_num(row.get('minimum_sales')), get_currency())}: {row.get('commission_percent', 0)}%")

    with adjustment_tab:
        if not active:
            st.info("No hay colaboradores activos.")
        else:
            options = {f"{member.get('name')} · {member.get('member_id')}": member for member in active}
            with st.form("commission_adjustment_form", clear_on_submit=True):
                selected = st.selectbox("Colaborador", tuple(options.keys()))
                kind = st.selectbox("Tipo", ("Anticipo", "Penalización/Ajuste"))
                amount = st.number_input("Monto", min_value=0.01, value=1.0, step=1.0)
                target_period = st.text_input("Periodo", value=period)
                responsible = st.text_input("Responsable")
                reason = st.text_area("Motivo", max_chars=500)
                submitted = st.form_submit_button("Guardar", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not reason.strip():
                    st.error("Responsable y motivo son obligatorios.")
                else:
                    member_id = str(options[selected].get("member_id", ""))
                    row = {
                        "member_id": member_id,
                        "period": target_period.strip() or period,
                        "amount": float(amount),
                        "responsible": responsible.strip(),
                        "reason": reason.strip(),
                        "status": "Activo",
                        "created_at_utc": _now(),
                    }
                    if kind == "Anticipo":
                        advances.append({"advance_id": f"ADV-{uuid4().hex[:8].upper()}", **row})
                        _save("commission_advances", advances)
                    else:
                        penalties.append({"penalty_id": f"ADJ-{uuid4().hex[:8].upper()}", **row})
                        _save("commission_penalties", penalties)
                    st.rerun()
        st.markdown("#### Anticipos")
        for row in reversed(advances[-50:]):
            st.write(f"**{_member_name(str(row.get('member_id', '')), members)}** · {row.get('period', '')} · {format_money(_num(row.get('amount')), get_currency())} · {row.get('reason', '')}")
        st.markdown("#### Ajustes / penalizaciones")
        for row in reversed(penalties[-50:]):
            st.write(f"**{_member_name(str(row.get('member_id', '')), members)}** · {row.get('period', '')} · {format_money(_num(row.get('amount')), get_currency())} · {row.get('reason', '')}")

    with simulation_tab:
        st.caption("Simula cuánto pagaría el negocio si cambian ventas, porcentaje o anticipos antes de generar pagos reales.")
        if not active:
            st.info("No hay colaboradores activos.")
        else:
            options = {f"{member.get('name')} · {member.get('member_id')}": member for member in active}
            with st.form("commission_simulation_form", clear_on_submit=True):
                selected = st.selectbox("Colaborador", tuple(options.keys()), key="sim_member")
                projected_sales = st.number_input("Ventas proyectadas", min_value=0.0, value=100.0, step=10.0)
                commission_percent = st.number_input("Comisión simulada %", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
                simulated_advances = st.number_input("Anticipos/descuentos", min_value=0.0, value=0.0, step=1.0)
                note = st.text_input("Nota")
                submitted = st.form_submit_button("Guardar simulación", type="primary", use_container_width=True)
            if submitted:
                member_id = str(options[selected].get("member_id", ""))
                gross = float(projected_sales) * float(commission_percent) / 100.0
                simulations.append({
                    "simulation_id": f"SIM-{uuid4().hex[:8].upper()}",
                    "member_id": member_id,
                    "period": period,
                    "projected_sales": float(projected_sales),
                    "commission_percent": float(commission_percent),
                    "gross_commission": gross,
                    "deductions": float(simulated_advances),
                    "net_commission": max(gross - float(simulated_advances), 0.0),
                    "note": note.strip(),
                    "created_at_utc": _now(),
                })
                _save("commission_simulations", simulations)
                st.rerun()
        for row in reversed(simulations[-50:]):
            st.write(f"**{row.get('simulation_id', '')} · {_member_name(str(row.get('member_id', '')), members)}** — neto {format_money(_num(row.get('net_commission')), get_currency())}")

    with receipt_tab:
        st.download_button("Descargar recibos CSV", data=_export_receipts(receipts), file_name=f"recibos_comision_{period}.csv", mime="text/csv", use_container_width=True, disabled=not receipts)
        for row in balances:
            locked = _is_locked(row["member_id"], period, locks)
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row['name']} · {period}**")
                cols[0].caption(row["commission_source"])
                cols[1].metric("Comisión", format_money(row["commission"], get_currency()))
                cols[2].metric("Deducciones", format_money(row["advances"] + row["penalties"], get_currency()))
                cols[3].metric("Neto", format_money(row["net_pending"], get_currency()))
                if st.button("Generar recibo", key=f"receipt_{row['member_id']}_{period}", use_container_width=True, disabled=locked or row["net_pending"] <= 0):
                    receipt_id = f"RCP-{uuid4().hex[:8].upper()}"
                    receipts.append({
                        "receipt_id": receipt_id,
                        "period": period,
                        "member_id": row["member_id"],
                        "member_name": row["name"],
                        "sales_total": row["sales_total"],
                        "commission": row["commission"],
                        "advances": row["advances"],
                        "penalties": row["penalties"],
                        "paid_period": row["paid_period"],
                        "net_pending": row["net_pending"],
                        "status": "Emitido",
                        "created_at_utc": _now(),
                    })
                    locks.append({
                        "lock_id": f"LCK-{uuid4().hex[:8].upper()}",
                        "member_id": row["member_id"],
                        "period": period,
                        "receipt_id": receipt_id,
                        "active": True,
                        "created_at_utc": _now(),
                    })
                    _save("commission_receipts", receipts)
                    _save("commission_payment_locks", locks)
                    st.rerun()

    with lock_tab:
        if not locks:
            st.info("No hay bloqueos registrados.")
        for row in reversed(locks[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1])
                cols[0].markdown(f"**{_member_name(str(row.get('member_id', '')), members)} · {row.get('period', '')}**")
                cols[0].caption(f"Recibo {row.get('receipt_id', '')} · {'Activo' if row.get('active', True) else 'Liberado'}")
                if cols[1].button("Liberar", key=f"unlock_commission_{row.get('lock_id')}", use_container_width=True, disabled=not row.get("active", True)):
                    changed = []
                    for item in locks:
                        current = dict(item)
                        if current.get("lock_id") == row.get("lock_id"):
                            current["active"] = False
                            current["released_at_utc"] = _now()
                        changed.append(current)
                    _save("commission_payment_locks", changed)
                    st.rerun()

    render_info_card(
        "Pago protegido",
        "Las comisiones ahora pueden simularse, ajustarse, recibirse y bloquearse para evitar doble pago.",
        "GOBIERNO DE COMISIONES",
    )


app_shell.FUNCTIONAL_MODULES["Equipo y comisiones"] = render_team_commission_governance
