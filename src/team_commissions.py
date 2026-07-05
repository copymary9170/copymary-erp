"""Equipo, comisiones y pagos internos para CopyMary ERP."""

from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _records(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, value: list[dict]) -> None:
    st.session_state[key] = value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _member_name(member_id: str, members: list[dict]) -> str:
    for member in members:
        if str(member.get("member_id", "")) == member_id:
            return str(member.get("name", "Colaborador"))
    return "Colaborador no disponible"


def _earned_for(member: dict, sales: list[dict]) -> float:
    paid_sales = [sale for sale in sales if sale.get("payment_status") == "Pagado" and sale.get("order_status") != "Cancelado"]
    mode = str(member.get("commission_mode", "Porcentaje"))
    value = float(member.get("commission_value", 0.0))
    if mode == "Porcentaje":
        return sum(float(sale.get("total", 0.0)) * value / 100 for sale in paid_sales)
    return len(paid_sales) * value


def _paid_to(member_id: str, payments: list[dict]) -> float:
    return sum(float(item.get("amount", 0.0)) for item in payments if str(item.get("member_id", "")) == member_id)


def render_team_commissions() -> None:
    with st.container(border=True):
        render_page_header(
            "Equipo y comisiones",
            "Registra colaboradores, calcula comisiones y controla pagos internos.",
        )
        st.caption("Los pagos al personal generan egresos en Caja y se incluyen en el Respaldo general.")

    members = _records("team_members")
    payments = _records("team_payments")
    sales = _records("sales_registry")
    cash = _records("cash_movements")

    total_earned = sum(_earned_for(member, sales) for member in members)
    total_paid = sum(float(item.get("amount", 0.0)) for item in payments)
    active_members = [member for member in members if member.get("active", True)]

    metrics = st.columns(4)
    metrics[0].metric("Colaboradores activos", str(len(active_members)))
    metrics[1].metric("Comisiones generadas", format_money(total_earned))
    metrics[2].metric("Pagado al equipo", format_money(total_paid))
    metrics[3].metric("Pendiente", format_money(max(total_earned - total_paid, 0.0)))

    tab_members, tab_payments, tab_history = st.tabs(("Equipo", "Registrar pago", "Historial"))

    with tab_members:
        with st.form("team_member_form", clear_on_submit=True):
            row = st.columns(4)
            name = row[0].text_input("Nombre", max_chars=100)
            role = row[1].text_input("Cargo o función", max_chars=100)
            mode = row[2].selectbox("Tipo de comisión", ("Porcentaje", "Monto por venta"))
            value = row[3].number_input("Valor", min_value=0.0, value=0.0, step=1.0)
            notes = st.text_input("Notas", max_chars=180)
            submitted = st.form_submit_button("Registrar colaborador", type="primary", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("El nombre es obligatorio.")
            else:
                members.append(
                    {
                        "member_id": uuid4().hex[:10],
                        "created_at_utc": _now(),
                        "name": name.strip(),
                        "role": role.strip(),
                        "commission_mode": mode,
                        "commission_value": float(value),
                        "notes": notes.strip(),
                        "active": True,
                    }
                )
                _save("team_members", members)
                st.rerun()

        for member in members:
            member_id = str(member.get("member_id", ""))
            earned = _earned_for(member, sales)
            paid = _paid_to(member_id, payments)
            with st.container(border=True):
                row = st.columns(5)
                row[0].metric("Nombre", str(member.get("name", "")))
                row[1].metric("Función", str(member.get("role") or "Sin definir"))
                row[2].metric("Generado", format_money(earned))
                row[3].metric("Pagado", format_money(paid))
                row[4].metric("Pendiente", format_money(max(earned - paid, 0.0)))
                st.caption(
                    f"{member.get('commission_mode', '')}: {member.get('commission_value', 0)} · "
                    f"Estado: {'Activo' if member.get('active', True) else 'Pausado'}"
                )
                if st.button(
                    "Pausar" if member.get("active", True) else "Activar",
                    key=f"toggle_member_{member_id}",
                    use_container_width=True,
                ):
                    updated = []
                    for current in members:
                        item = dict(current)
                        if current.get("member_id") == member_id:
                            item["active"] = not bool(current.get("active", True))
                        updated.append(item)
                    _save("team_members", updated)
                    st.rerun()

    with tab_payments:
        if not members:
            st.info("Registra primero un colaborador.")
        else:
            options = {f"{member.get('name', '')} · {member.get('role', '')}": member for member in active_members}
            if not options:
                st.info("No hay colaboradores activos.")
            else:
                with st.form("team_payment_form", clear_on_submit=True):
                    selected_label = st.selectbox("Colaborador", tuple(options.keys()))
                    selected = options[selected_label]
                    member_id = str(selected.get("member_id", ""))
                    pending = max(_earned_for(selected, sales) - _paid_to(member_id, payments), 0.0)
                    row = st.columns(4)
                    amount = row[0].number_input("Monto", min_value=0.01, value=max(pending, 0.01), step=1.0)
                    method = row[1].selectbox("Método", ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro"))
                    payment_date = row[2].date_input("Fecha", value=date.today())
                    reference = row[3].text_input("Referencia", max_chars=80)
                    notes = st.text_input("Concepto", value="Pago de comisión", max_chars=180)
                    submitted = st.form_submit_button("Registrar pago", type="primary", use_container_width=True)

                if submitted:
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
                            "notes": notes.strip(),
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
                            "notes": f"{_member_name(member_id, members)}: {notes.strip()}",
                        }
                    )
                    _save("team_payments", payments)
                    _save("cash_movements", cash)
                    st.rerun()

    with tab_history:
        if not payments:
            st.info("Todavía no hay pagos registrados.")
        else:
            for payment in reversed(payments):
                with st.container(border=True):
                    row = st.columns([3, 1])
                    row[0].markdown(f"### {_member_name(str(payment.get('member_id', '')), members)}")
                    row[0].caption(
                        f"{payment.get('payment_date', '')} · {payment.get('payment_method', '')} · "
                        f"Ref. {payment.get('reference') or 'Sin referencia'}"
                    )
                    row[1].metric("Pago", format_money(float(payment.get("amount", 0.0))))

    render_info_card(
        "Cálculo provisional",
        "Las comisiones se calculan sobre ventas pagadas de la sesión y no sustituyen una nómina legal.",
        "CONTROL INTERNO",
    )
