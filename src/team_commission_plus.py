"""Equipo y comisiones avanzado con metas, cortes y control de pagos."""

from collections import defaultdict
from datetime import date
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup, team_commission_control as base
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("team_roles", "Roles del equipo"),
        ("team_targets", "Metas del equipo"),
        ("commission_periods", "Cortes de comisiones"),
        ("commission_payment_requests", "Solicitudes de pago de comisiones"),
        ("commission_audit_log", "Auditoría de comisiones"),
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


def _period_key(value: date | None = None) -> str:
    current = value or date.today()
    return f"{current.year:04d}-{current.month:02d}"


def _member_name(member_id: str, members: list[dict]) -> str:
    return base._name(member_id, members)


def _earned(member: dict, assignments: list[dict], sales: list[dict]) -> float:
    return base._earned(member, assignments, sales)


def _paid(member_id: str, payments: list[dict]) -> float:
    return base._paid(member_id, payments)


def _assignment_commission(item: dict) -> float:
    return base._assignment_commission(item)


def _sale_date(sale: dict) -> str:
    return str(sale.get("created_at_utc", sale.get("sale_date", "")))[:10]


def _in_period(value: str, period: str) -> bool:
    return str(value or "")[:7] == period


def _assignment_period_value(member_id: str, assignments: list[dict], sales: list[dict], period: str) -> tuple[int, float, float]:
    sale_map = {str(sale.get("sale_id", "")): sale for sale in sales}
    count = 0
    sales_total = 0.0
    commission_total = 0.0
    for assignment in assignments:
        if str(assignment.get("member_id", "")) != member_id or not assignment.get("active", True):
            continue
        sale = sale_map.get(str(assignment.get("sale_id", "")), {})
        if sale.get("order_status") == "Cancelado" or sale.get("payment_status") != "Pagado":
            continue
        if not _in_period(_sale_date(sale), period):
            continue
        count += 1
        sales_total += _num(sale.get("total", assignment.get("sale_total_snapshot", 0.0)))
        commission_total += _assignment_commission(assignment)
    return count, sales_total, commission_total


def _audit(action: str, member_id: str, responsible: str, note: str) -> None:
    rows = _rows("commission_audit_log")
    rows.append({
        "audit_id": f"TCA-{uuid4().hex[:8].upper()}",
        "action": action,
        "member_id": member_id,
        "responsible": responsible.strip() or "Sin asignar",
        "note": note.strip(),
        "created_at_utc": _now(),
    })
    _save("commission_audit_log", rows)


def _export_balances(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Colaborador", "Rol", "Generado", "Pagado", "Pendiente", "Ventas", "Meta", "Cumplimiento %"])
    for row in rows:
        writer.writerow([
            row.get("name", ""), row.get("role", ""), row.get("earned", 0), row.get("paid", 0),
            row.get("pending", 0), row.get("sales_total", 0), row.get("target", 0), row.get("achievement", 0),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_team_commission_plus() -> None:
    render_page_header(
        "Equipo y comisiones",
        "Controla roles, metas, cortes, solicitudes de pago y auditoría de comisiones.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_team_commission_control()
    finally:
        base.render_page_header = original_header

    members = _rows("team_members")
    payments = _rows("team_payments")
    assignments = _rows("commission_assignments")
    sales = _rows("sales_registry")
    roles = _rows("team_roles")
    targets = _rows("team_targets")
    periods = _rows("commission_periods")
    requests = _rows("commission_payment_requests")
    audit = _rows("commission_audit_log")
    period = _period_key()
    active = [member for member in members if member.get("active", True)]
    pending_requests = [row for row in requests if row.get("status") == "Pendiente"]
    role_by_member = {str(row.get("member_id", "")): row for row in roles if row.get("active", True)}
    target_by_member = {str(row.get("member_id", "")): row for row in targets if row.get("period") == period and row.get("active", True)}

    balances = []
    for member in members:
        member_id = str(member.get("member_id", ""))
        count, sales_total, commission_period = _assignment_period_value(member_id, assignments, sales, period)
        earned_total = _earned(member, assignments, sales)
        paid_total = _paid(member_id, payments)
        target = _num(target_by_member.get(member_id, {}).get("sales_target"))
        balances.append({
            "member_id": member_id,
            "name": str(member.get("name", "Colaborador")),
            "role": str(role_by_member.get(member_id, {}).get("role", "Sin rol")),
            "earned": earned_total,
            "paid": paid_total,
            "pending": max(earned_total - paid_total, 0.0),
            "period_commission": commission_period,
            "sales_total": sales_total,
            "sales_count": count,
            "target": target,
            "achievement": sales_total / target * 100.0 if target else 0.0,
        })

    st.divider()
    st.markdown("### Control avanzado de equipo")
    metrics = st.columns(5)
    metrics[0].metric("Activos", str(len(active)))
    metrics[1].metric("Pendiente total", format_money(sum(row["pending"] for row in balances), get_currency()))
    metrics[2].metric("Comisión del mes", format_money(sum(row["period_commission"] for row in balances), get_currency()))
    metrics[3].metric("Solicitudes pago", str(len(pending_requests)))
    metrics[4].metric("Cortes guardados", str(len(periods)))

    role_tab, target_tab, cut_tab, request_tab, audit_tab = st.tabs(("Roles", "Metas", "Corte", "Solicitudes", "Auditoría"))

    with role_tab:
        if not members:
            st.info("Primero registra colaboradores.")
        else:
            member_options = {f"{member.get('name', 'Colaborador')} · {member.get('member_id', '')}": member for member in members}
            with st.form("team_role_form", clear_on_submit=True):
                selected = st.selectbox("Colaborador", tuple(member_options.keys()))
                role = st.text_input("Rol", placeholder="Diseño, ventas, producción, apoyo")
                supervisor = st.text_input("Supervisor o responsable")
                note = st.text_input("Nota")
                submitted = st.form_submit_button("Guardar rol", type="primary", use_container_width=True)
            if submitted:
                if not role.strip():
                    st.error("Indica el rol.")
                else:
                    member = member_options[selected]
                    member_id = str(member.get("member_id", ""))
                    for row in roles:
                        if str(row.get("member_id", "")) == member_id:
                            row["active"] = False
                            row["ended_at_utc"] = _now()
                    roles.append({
                        "role_id": f"ROL-{uuid4().hex[:8].upper()}",
                        "member_id": member_id,
                        "role": role.strip(),
                        "supervisor": supervisor.strip(),
                        "note": note.strip(),
                        "active": True,
                        "created_at_utc": _now(),
                    })
                    _save("team_roles", roles)
                    _audit("Rol actualizado", member_id, supervisor or "Sistema", role)
                    st.rerun()
        for row in balances:
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row['name']}**")
                cols[0].caption(f"Rol: {row['role']} · ID {row['member_id']}")
                cols[1].metric("Ventas mes", format_money(row["sales_total"], get_currency()))
                cols[2].metric("Comisión mes", format_money(row["period_commission"], get_currency()))
                cols[3].metric("Pendiente", format_money(row["pending"], get_currency()))

    with target_tab:
        if not active:
            st.info("No hay colaboradores activos.")
        else:
            options = {f"{member.get('name', 'Colaborador')} · {member.get('member_id', '')}": member for member in active}
            with st.form("team_target_form", clear_on_submit=True):
                selected = st.selectbox("Colaborador", tuple(options.keys()))
                target_period = st.text_input("Periodo", value=period)
                sales_target = st.number_input("Meta de ventas", min_value=0.0, value=0.0, step=1.0)
                commission_bonus = st.number_input("Bono por cumplir meta", min_value=0.0, value=0.0, step=1.0)
                responsible = st.text_input("Responsable")
                submitted = st.form_submit_button("Guardar meta", type="primary", use_container_width=True)
            if submitted:
                if sales_target <= 0 or not responsible.strip():
                    st.error("Meta y responsable son obligatorios.")
                else:
                    member_id = str(options[selected].get("member_id", ""))
                    targets.append({
                        "target_id": f"TGT-{uuid4().hex[:8].upper()}",
                        "member_id": member_id,
                        "period": target_period.strip() or period,
                        "sales_target": float(sales_target),
                        "commission_bonus": float(commission_bonus),
                        "responsible": responsible.strip(),
                        "active": True,
                        "created_at_utc": _now(),
                    })
                    _save("team_targets", targets)
                    _audit("Meta asignada", member_id, responsible, f"Meta {sales_target:,.2f}")
                    st.rerun()
        for row in balances:
            if row["target"] <= 0:
                continue
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row['name']}**")
                cols[1].metric("Meta", format_money(row["target"], get_currency()))
                cols[2].metric("Vendido", format_money(row["sales_total"], get_currency()))
                cols[3].metric("Cumplimiento", f"{row['achievement']:,.1f}%")
                if row["achievement"] >= 100:
                    st.success("Meta cumplida.")
                elif row["achievement"] >= 75:
                    st.warning("Meta en riesgo: faltan ventas para cerrar el periodo.")

    with cut_tab:
        st.download_button(
            "Descargar saldos CSV",
            data=_export_balances(balances),
            file_name=f"equipo_comisiones_{period}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not balances,
        )
        if st.button("Crear corte de comisiones del periodo", type="primary", use_container_width=True, disabled=not balances):
            periods.append({
                "period_id": f"CPC-{uuid4().hex[:8].upper()}",
                "period": period,
                "rows": balances,
                "total_pending": sum(row["pending"] for row in balances),
                "total_period_commission": sum(row["period_commission"] for row in balances),
                "created_at_utc": _now(),
            })
            _save("commission_periods", periods)
            st.rerun()
        for item in reversed(periods[-50:]):
            st.write(f"**{item.get('period_id', '')} · {item.get('period', '')}** · pendiente {format_money(_num(item.get('total_pending')), get_currency())} · comisión mes {format_money(_num(item.get('total_period_commission')), get_currency())}")

    with request_tab:
        payable = [row for row in balances if row["pending"] > 0.01]
        if not payable:
            st.info("No hay saldos pendientes para solicitar pago.")
        else:
            options = {f"{row['name']} · pendiente {format_money(row['pending'], get_currency())}": row for row in payable}
            with st.form("commission_payment_request_form", clear_on_submit=True):
                selected = st.selectbox("Colaborador", tuple(options.keys()))
                amount = st.number_input("Monto solicitado", min_value=0.01, value=min(options[selected]["pending"], 1.0), step=1.0)
                requested_by = st.text_input("Solicitado por")
                reason = st.text_area("Motivo", max_chars=500)
                submitted = st.form_submit_button("Crear solicitud de pago", type="primary", use_container_width=True)
            if submitted:
                selected_row = options[selected]
                if amount > selected_row["pending"] + 0.0001:
                    st.error("La solicitud no puede superar el saldo pendiente.")
                elif not requested_by.strip() or not reason.strip():
                    st.error("Solicitante y motivo son obligatorios.")
                else:
                    requests.append({
                        "request_id": f"CPR-{uuid4().hex[:8].upper()}",
                        "member_id": selected_row["member_id"],
                        "amount": float(amount),
                        "pending_at_request": selected_row["pending"],
                        "requested_by": requested_by.strip(),
                        "reason": reason.strip(),
                        "status": "Pendiente",
                        "created_at_utc": _now(),
                    })
                    _save("commission_payment_requests", requests)
                    _audit("Solicitud de pago", selected_row["member_id"], requested_by, reason)
                    st.rerun()
        for request in reversed(requests[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{request.get('request_id', '')} · {_member_name(str(request.get('member_id', '')), members)}**")
                cols[0].caption(f"{request.get('requested_by', '')} · {request.get('reason', '')}")
                cols[1].metric("Monto", format_money(_num(request.get("amount")), get_currency()))
                cols[2].metric("Estado", str(request.get("status", "")))
                if request.get("status") == "Pendiente":
                    decision_cols = st.columns(2)
                    if decision_cols[0].button("Aprobar", key=f"approve_commission_request_{request.get('request_id')}", use_container_width=True):
                        changed = []
                        for row in requests:
                            current = dict(row)
                            if current.get("request_id") == request.get("request_id"):
                                current["status"] = "Aprobada"
                                current["approved_at_utc"] = _now()
                            changed.append(current)
                        _save("commission_payment_requests", changed)
                        _audit("Solicitud aprobada", str(request.get("member_id", "")), "Sistema", str(request.get("request_id", "")))
                        st.rerun()
                    if decision_cols[1].button("Rechazar", key=f"reject_commission_request_{request.get('request_id')}", use_container_width=True):
                        changed = []
                        for row in requests:
                            current = dict(row)
                            if current.get("request_id") == request.get("request_id"):
                                current["status"] = "Rechazada"
                                current["rejected_at_utc"] = _now()
                            changed.append(current)
                        _save("commission_payment_requests", changed)
                        _audit("Solicitud rechazada", str(request.get("member_id", "")), "Sistema", str(request.get("request_id", "")))
                        st.rerun()

    with audit_tab:
        if not audit:
            st.info("No hay auditoría adicional de comisiones.")
        for item in reversed(audit[-150:]):
            st.write(f"**{item.get('action', '')}** · {_member_name(str(item.get('member_id', '')), members)} · {item.get('responsible', '')} · {item.get('created_at_utc', '')} — {item.get('note', '')}")

    render_info_card(
        "Comisiones trazables",
        "El equipo ahora tiene roles, metas, cortes y solicitudes de pago antes de ejecutar comisiones.",
        "GESTIÓN DE EQUIPO",
    )


app_shell.FUNCTIONAL_MODULES["Equipo y comisiones"] = render_team_commission_plus
