"""Comisiones calculadas por ventas asignadas y mantenimiento del equipo."""

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


def _member_label(member: dict) -> str:
    return f"{member.get('name', 'Colaborador')} · {member.get('member_id', '')}"


def _assignment_commission(item: dict) -> float:
    value = float(item.get("commission_value_snapshot", 0.0))
    if item.get("commission_mode_snapshot") == "Monto por venta":
        return value
    return float(item.get("sale_total_snapshot", 0.0)) * value / 100


def _earned(member: dict, assignments: list[dict], sales: list[dict]) -> float:
    member_id = str(member.get("member_id", ""))
    sale_ids = {
        str(item.get("sale_id", ""))
        for item in assignments
        if str(item.get("member_id", "")) == member_id and item.get("active", True)
    }
    paid_sales = [
        sale
        for sale in sales
        if str(sale.get("sale_id", "")) in sale_ids
        and sale.get("payment_status") == "Pagado"
        and sale.get("order_status") != "Cancelado"
    ]
    value = float(member.get("commission_value", 0.0))
    if member.get("commission_mode") == "Monto por venta":
        return len(paid_sales) * value
    return sum(float(sale.get("total", 0.0)) * value / 100 for sale in paid_sales)


def _paid(member_id: str, payments: list[dict]) -> float:
    return sum(
        float(item.get("amount", 0.0))
        for item in payments
        if str(item.get("member_id", "")) == member_id and not item.get("reversed")
    )


def render_team_commission_control() -> None:
    with st.container(border=True):
        render_page_header(
            "Equipo y comisiones",
            "Administra colaboradores y calcula comisiones solo sobre ventas pagadas asignadas.",
        )

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
        with st.form("new_team_member", clear_on_submit=True):
            st.markdown("### Registrar colaborador")
            row = st.columns(3)
            name = row[0].text_input("Nombre", max_chars=100)
            mode = row[1].selectbox("Tipo de comisión", ("Porcentaje", "Monto por venta"))
            value = row[2].number_input("Valor", min_value=0.0, value=0.0, step=1.0)
            create_member = st.form_submit_button("Agregar colaborador", type="primary", use_container_width=True)

        if create_member:
            cleaned_name = name.strip()
            if not cleaned_name:
                st.error("El nombre no puede quedar vacío.")
            elif mode == "Porcentaje" and float(value) > 100:
                st.error("El porcentaje no puede superar 100%.")
            else:
                members.append(
                    {
                        "member_id": uuid4().hex[:10],
                        "created_at_utc": _now(),
                        "name": cleaned_name,
                        "commission_mode": mode,
                        "commission_value": float(value),
                        "active": True,
                    }
                )
                st.session_state["team_members"] = members
                st.rerun()

        if not members:
            st.info("Todavía no hay colaboradores registrados.")

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
                st.caption(
                    f"ID {member_id} · {member.get('commission_mode', 'Porcentaje')}: "
                    f"{member.get('commission_value', 0)} · "
                    f"{'Activo' if member.get('active', True) else 'Pausado'}"
                )

                with st.form(f"edit_team_member_{member_id}"):
                    edit = st.columns(3)
                    edited_name = edit[0].text_input(
                        "Nombre",
                        value=str(member.get("name", "")),
                        key=f"member_name_{member_id}",
                    )
                    edited_mode = edit[1].selectbox(
                        "Tipo de comisión",
                        ("Porcentaje", "Monto por venta"),
                        index=0 if member.get("commission_mode") != "Monto por venta" else 1,
                        key=f"member_mode_{member_id}",
                    )
                    edited_value = edit[2].number_input(
                        "Valor",
                        min_value=0.0,
                        value=float(member.get("commission_value", 0.0)),
                        step=1.0,
                        key=f"member_value_{member_id}",
                    )
                    save_member = st.form_submit_button("Guardar cambios", use_container_width=True)

                controls = st.columns(2)
                toggle_label = "Pausar" if member.get("active", True) else "Activar"
                toggle_member = controls[0].button(
                    toggle_label,
                    key=f"toggle_member_{member_id}",
                    use_container_width=True,
                )
                controls[1].caption("Pausar conserva pagos, asignaciones e historial.")

                if save_member:
                    if not edited_name.strip():
                        st.error("El nombre no puede quedar vacío.")
                    elif edited_mode == "Porcentaje" and float(edited_value) > 100:
                        st.error("El porcentaje no puede superar 100%.")
                    else:
                        for current in members:
                            if str(current.get("member_id", "")) == member_id:
                                current["name"] = edited_name.strip()
                                current["commission_mode"] = edited_mode
                                current["commission_value"] = float(edited_value)
                        st.session_state["team_members"] = members
                        st.rerun()

                if toggle_member:
                    for current in members:
                        if str(current.get("member_id", "")) == member_id:
                            current["active"] = not bool(current.get("active", True))
                    st.session_state["team_members"] = members
                    st.rerun()

    with assign_tab:
        available_sales = [sale for sale in sales if sale.get("order_status") != "Cancelado"]
        if not active or not available_sales:
            st.info("Necesitas colaboradores activos y ventas disponibles.")
        else:
            member_options = {_member_label(member): member for member in active}
            sale_options = {
                f"{sale.get('description', 'Venta')} · {format_money(float(sale.get('total', 0.0)))} · {sale.get('sale_id', '')}": sale
                for sale in available_sales
            }
            with st.form("assign_commission_sale"):
                member = member_options[st.selectbox("Colaborador", tuple(member_options.keys()))]
                sale = sale_options[st.selectbox("Venta", tuple(sale_options.keys()))]
                submitted = st.form_submit_button("Asignar venta", type="primary", use_container_width=True)
            if submitted:
                member_id = str(member.get("member_id", ""))
                sale_id = str(sale.get("sale_id", ""))
                exists = any(
                    str(item.get("member_id", "")) == member_id
                    and str(item.get("sale_id", "")) == sale_id
                    and item.get("active", True)
                    for item in assignments
                )
                if exists:
                    st.warning("La venta ya está asignada a este colaborador.")
                else:
                    assignments.append(
                        {
                            "assignment_id": uuid4().hex[:10],
                            "created_at_utc": _now(),
                            "member_id": member_id,
                            "sale_id": sale_id,
                            "commission_mode_snapshot": str(member.get("commission_mode", "Porcentaje")),
                            "commission_value_snapshot": float(member.get("commission_value", 0.0)),
                            "sale_total_snapshot": float(sale.get("total", 0.0)),
                            "sale_description_snapshot": str(sale.get("description", "Venta")),
                            "active": True,
                        }
                    )
                    st.session_state["commission_assignments"] = assignments
                    st.rerun()

        if assignments:
            sale_map = {str(sale.get("sale_id", "")): sale for sale in sales}
            for item in reversed(assignments):
                if not item.get("active", True):
                    continue
                sale = sale_map.get(str(item.get("sale_id", "")), {})
                description = str(
                    item.get("sale_description_snapshot", sale.get("description", "Venta"))
                )
                with st.container(border=True):
                    row = st.columns([3, 1])
                    row[0].write(
                        f"**{_name(str(item.get('member_id', '')), members)}** · {description}"
                    )
                    row[1].metric("Comisión", format_money(_assignment_commission(item)))
                    details = st.columns(3)
                    details[0].metric(
                        "Venta guardada",
                        format_money(float(item.get("sale_total_snapshot", sale.get("total", 0.0)))),
                    )
                    details[1].metric(
                        "Tipo",
                        str(item.get("commission_mode_snapshot", "Porcentaje")),
                    )
                    details[2].metric(
                        "Valor",
                        str(item.get("commission_value_snapshot", 0.0)),
                    )
                    if row[1].button(
                        "Quitar",
                        key=f"remove_assignment_{item.get('assignment_id')}",
                        use_container_width=True,
                    ):
                        for current in assignments:
                            if current.get("assignment_id") == item.get("assignment_id"):
                                current["active"] = False
                        st.session_state["commission_assignments"] = assignments
                        st.rerun()

    with pay_tab:
        if not active:
            st.info("No hay colaboradores activos.")
        else:
            options = {_member_label(member): member for member in active}
            selected = options[
                st.selectbox("Colaborador", tuple(options.keys()), key="commission_member_to_pay")
            ]
            member_id = str(selected.get("member_id", ""))
            pending = max(_earned(selected, assignments, sales) - _paid(member_id, payments), 0.0)
            st.metric("Saldo pendiente", format_money(pending))
            with st.form("commission_payment_form", clear_on_submit=True):
                row = st.columns(4)
                amount = row[0].number_input(
                    "Monto",
                    min_value=0.01,
                    value=max(min(pending, 1.0), 0.01),
                    step=1.0,
                )
                method = row[1].selectbox(
                    "Método",
                    ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro"),
                )
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
                    payments.append(
                        {
                            "payment_id": payment_id,
                            "created_at_utc": created,
                            "payment_date": payment_date.isoformat(),
                            "member_id": member_id,
                            "amount": float(amount),
                            "payment_method": method,
                            "reference": reference.strip(),
                            "reversed": False,
                        }
                    )
                    cash.append(
                        {
                            "movement_id": uuid4().hex[:10],
                            "created_at_utc": created,
                            "movement_type": "Egreso",
                            "category": "Pago al personal",
                            "amount": float(amount),
                            "payment_method": method,
                            "reference": payment_id,
                            "notes": _name(member_id, members),
                        }
                    )
                    st.session_state["team_payments"] = payments
                    st.session_state["cash_movements"] = cash
                    st.rerun()

    with history_tab:
        if not payments:
            st.info("Todavía no hay pagos registrados.")
        for payment in reversed(payments):
            with st.container(border=True):
                row = st.columns([3, 1])
                status = "REVERTIDO" if payment.get("reversed") else "ACTIVO"
                row[0].write(
                    f"**{_name(str(payment.get('member_id', '')), members)}** · "
                    f"{payment.get('payment_date', '')} · {payment.get('payment_method', '')} · {status}"
                )
                row[1].metric("Pago", format_money(float(payment.get("amount", 0.0))))

    render_info_card(
        "Cálculo controlado",
        "Cada persona genera comisión solo por sus ventas asignadas y pagadas.",
        "CONTROL INTERNO",
    )
