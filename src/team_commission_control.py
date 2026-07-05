"""Comisiones calculadas por ventas asignadas."""

from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _name(member_id: str, members: list[dict]) -> str:
    for member in members:
        if str(member.get("member_id", "")) == member_id:
            return str(member.get("name", "Colaborador"))
    return "Colaborador"


def _earned(member: dict, assignments: list[dict], sales: list[dict]) -> float:
    member_id = str(member.get("member_id", ""))
    sale_ids = {str(item.get("sale_id", "")) for item in assignments if str(item.get("member_id", "")) == member_id and item.get("active", True)}
    paid_sales = [sale for sale in sales if str(sale.get("sale_id", "")) in sale_ids and sale.get("payment_status") == "Pagado" and sale.get("order_status") != "Cancelado"]
    value = float(member.get("commission_value", 0.0))
    if member.get("commission_mode") == "Monto por venta":
        return len(paid_sales) * value
    return sum(float(sale.get("total", 0.0)) * value / 100 for sale in paid_sales)


def _paid(member_id: str, payments: list[dict]) -> float:
    return sum(float(item.get("amount", 0.0)) for item in payments if str(item.get("member_id", "")) == member_id and not item.get("reversed"))


def render_team_commission_control() -> None:
    with st.container(border=True):
        render_page_header("Equipo y comisiones", "Calcula comisiones solo sobre ventas pagadas asignadas.")

    members = _rows("team_members")
    payments = _rows("team_payments")
    assignments = _rows("commission_assignments")
    sales = _rows("sales_registry")
    cash = _rows("cash_movements")
    active = [item for item in members if item.get("active", True)]

    total_earned = sum(_earned(member, assignments, sales) for member in members)
    total_paid = sum(float(item.get("amount", 0.0)) for item in payments if not item.get("reversed"))
    metrics = st.columns(4)
    metrics[0].metric("Activos", str(len(active)))
    metrics[1].metric("Generado", format_money(total_earned))
    metrics[2].metric("Pagado", format_money(total_paid))
    metrics[3].metric("Pendiente", format_money(max(total_earned - total_paid, 0.0)))

    team_tab, assign_tab, pay_tab, history_tab = st.tabs(("Equipo", "Asignaciones", "Pagar", "Historial"))

    with team_tab:
        for member in members:
            member_id = str(member.get("member_id", ""))
            earned = _earned(member, assignments, sales)
            paid = _paid(member_id, payments)
            with st.container(border=True):
                row = st.columns(4)
                row[0].metric("Nombre", str(member.get("name", "")))
                row[1].metric("Generado", format_money(earned))
                row[2].metric("Pagado", format_money(paid))
                row[3].metric("Pendiente", format_money(max(earned - paid, 0.0)))
                st.caption(f"{member.get('commission_mode', 'Porcentaje')}: {member.get('commission_value', 0)}")

    with assign_tab:
        available_sales = [sale for sale in sales if sale.get("order_status") != "Cancelado"]
        if not active or not available_sales:
            st.info("Necesitas colaboradores activos y ventas disponibles.")
        else:
            member_options = {str(member.get("name", "")): member for member in active}
            sale_options = {f"{sale.get('description', 'Venta')} · {format_money(float(sale.get('total', 0.0)))} · {sale.get('sale_id', '')}": sale for sale in available_sales}
            with st.form("assign_commission_sale"):
                member = member_options[st.selectbox("Colaborador", tuple(member_options.keys()))]
                sale = sale_options[st.selectbox("Venta", tuple(sale_options.keys()))]
                submitted = st.form_submit_button("Asignar venta", type="primary", use_container_width=True)
            if submitted:
                member_id = str(member.get("member_id", ""))
                sale_id = str(sale.get("sale_id", ""))
                exists = any(str(item.get("member_id", "")) == member_id and str(item.get("sale_id", "")) == sale_id and item.get("active", True) for item in assignments)
                if exists:
                    st.warning("La venta ya está asignada a este colaborador.")
                else:
                    assignments.append({"assignment_id": uuid4().hex[:10], "created_at_utc": _now(), "member_id": member_id, "sale_id": sale_id, "active": True})
                    st.session_state["commission_assignments"] = assignments
                    st.rerun()

        if assignments:
            sale_map = {str(sale.get("sale_id", "")): sale for sale in sales}
            for item in reversed(assignments):
                if not item.get("active", True):
                    continue
                sale = sale_map.get(str(item.get("sale_id", "")), {})
                with st.container(border=True):
                    row = st.columns([3, 1])
                    row[0].write(f"**{_name(str(item.get('member_id', '')), members)}** · {sale.get('description', 'Venta')}")
                    if row[1].button("Quitar", key=f"remove_assignment_{item.get('assignment_id')}", use_container_width=True):
                        for current in assignments:
                            if current.get("assignment_id") == item.get("assignment_id"):
                                current["active"] = False
                        st.session_state["commission_assignments"] = assignments
                        st.rerun()

    with pay_tab:
        if not active:
            st.info("No hay colaboradores activos.")
        else:
            options = {str(member.get("name", "")): member for member in active}
            selected = options[st.selectbox("Colaborador", tuple(options.keys()), key="commission_member_to_pay")]
            member_id = str(selected.get("member_id", ""))
            pending = max(_earned(selected, assignments, sales) - _paid(member_id, payments), 0.0)
            st.metric("Saldo pendiente", format_money(pending))
            with st.form("commission_payment_form", clear_on_submit=True):
                row = st.columns(4)
                amount = row[0].number_input("Monto", min_value=0.01, value=max(min(pending, 1.0), 0.01), step=1.0)
                method = row[1].selectbox("Método", ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro"))
                payment_date = row[2].date_input("Fecha", value=date.today())
                reference = row[3].text_input("Referencia", max_chars=80)
                submitted = st.form_submit_button("Registrar pago", type="primary", use_container_width=True)
            if submitted:
                if pending <= 0:
                    st.error("No hay comisiones pendientes.")
                elif float(amount) > pending + 0.0001:
                    st.error("El pago no puede superar el saldo pendiente.")
                else:
                    payment_id = uuid4().hex[:10]
                    created = _now()
                    payments.append({"payment_id": payment_id, "created_at_utc": created, "payment_date": payment_date.isoformat(), "member_id": member_id, "amount": float(amount), "payment_method": method, "reference": reference.strip(), "reversed": False})
                    cash.append({"movement_id": uuid4().hex[:10], "created_at_utc": created, "movement_type": "Egreso", "category": "Pago al personal", "amount": float(amount), "payment_method": method, "reference": payment_id, "notes": _name(member_id, members)})
                    st.session_state["team_payments"] = payments
                    st.session_state["cash_movements"] = cash
                    st.rerun()

    with history_tab:
        if not payments:
            st.info("Todavía no hay pagos registrados.")
        for payment in reversed(payments):
            with st.container(border=True):
                row = st.columns([3, 1])
                row[0].write(f"**{_name(str(payment.get('member_id', '')), members)}** · {payment.get('payment_date', '')} · {payment.get('payment_method', '')}")
                row[1].metric("Pago", format_money(float(payment.get("amount", 0.0))))

    render_info_card("Cálculo controlado", "Cada persona genera comisión solo por sus ventas asignadas y pagadas.", "CONTROL INTERNO")
