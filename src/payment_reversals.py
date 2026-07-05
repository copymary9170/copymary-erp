"""Reversos de abonos y pagos con trazabilidad de Caja."""

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_reversed(payment: dict) -> bool:
    return bool(payment.get("reversed"))


def _reverse_cash(cash: list[dict], payment: dict, movement_type: str, category: str, notes: str) -> list[dict]:
    payment_id = str(payment.get("payment_id", ""))
    if any(str(item.get("reference", "")) == f"REV-{payment_id}" for item in cash):
        return cash
    cash.append({
        "movement_id": uuid4().hex[:10],
        "created_at_utc": _now(),
        "movement_type": movement_type,
        "category": category,
        "amount": float(payment.get("amount", 0.0)),
        "payment_method": str(payment.get("payment_method", "Otro")),
        "reference": f"REV-{payment_id}",
        "notes": notes,
    })
    return cash


def _status(total: float, paid: float) -> str:
    if paid <= 0:
        return "Pendiente"
    if paid + 0.0001 >= total:
        return "Pagado"
    return "Abono"


def _active_paid(records: list[dict], link_key: str, link_id: str) -> float:
    return sum(
        float(item.get("amount", 0.0))
        for item in records
        if str(item.get(link_key, "")) == link_id and not _is_reversed(item)
    )


def _mark_reversed(records: list[dict], payment_id: str, reason: str) -> list[dict]:
    updated: list[dict] = []
    for record in records:
        current = dict(record)
        if str(record.get("payment_id", "")) == payment_id:
            current["reversed"] = True
            current["reversed_at_utc"] = _now()
            current["reversal_reason"] = reason
        updated.append(current)
    return updated


def render_payment_reversals() -> None:
    with st.container(border=True):
        render_page_header("Reversos de pagos", "Anula cobros y pagos sin borrar el historial original.")
        st.caption("Cada reverso crea el movimiento contrario en Caja y solo puede aplicarse una vez.")

    customer_payments = _rows("payment_records")
    supplier_payments = _rows("supplier_payment_records")
    team_payments = _rows("team_payments")
    sales = _rows("sales_registry")
    purchases = _rows("purchases_registry")
    members = _rows("team_members")
    cash = _rows("cash_movements")

    active_customer = [item for item in customer_payments if not _is_reversed(item)]
    active_supplier = [item for item in supplier_payments if not _is_reversed(item)]
    active_team = [item for item in team_payments if not _is_reversed(item)]

    metrics = st.columns(4)
    metrics[0].metric("Abonos de clientes", str(len(active_customer)))
    metrics[1].metric("Pagos a proveedores", str(len(active_supplier)))
    metrics[2].metric("Pagos al equipo", str(len(active_team)))
    metrics[3].metric("Reversos realizados", str(sum(1 for group in (customer_payments, supplier_payments, team_payments) for item in group if _is_reversed(item))))

    customer_tab, supplier_tab, team_tab, history_tab = st.tabs(("Clientes", "Proveedores", "Equipo", "Historial"))

    with customer_tab:
        if not active_customer:
            st.info("No hay abonos activos para revertir.")
        else:
            options = {f"{item.get('payment_date', '')} · {format_money(float(item.get('amount', 0.0)))} · {item.get('payment_id', '')}": item for item in active_customer}
            selected = options[st.selectbox("Abono", tuple(options.keys()))]
            reason = st.text_input("Motivo", key="customer_payment_reversal_reason", max_chars=200)
            if st.button("Revertir abono", type="primary", use_container_width=True):
                payment_id = str(selected.get("payment_id", ""))
                sale_id = str(selected.get("sale_id", ""))
                updated_payments = _mark_reversed(customer_payments, payment_id, reason.strip())
                cash = _reverse_cash(cash, selected, "Egreso", "Reverso de cobro", reason.strip() or f"Reverso de abono {payment_id}")
                updated_sales: list[dict] = []
                for sale in sales:
                    current = dict(sale)
                    if str(sale.get("sale_id", "")) == sale_id:
                        paid = _active_paid(updated_payments, "sale_id", sale_id)
                        current["payment_status"] = _status(float(sale.get("total", 0.0)), paid)
                        current["cash_registered"] = current["payment_status"] == "Pagado"
                    updated_sales.append(current)
                st.session_state["payment_records"] = updated_payments
                st.session_state["sales_registry"] = updated_sales
                st.session_state["cash_movements"] = cash
                st.rerun()

    with supplier_tab:
        if not active_supplier:
            st.info("No hay pagos activos para revertir.")
        else:
            options = {f"{item.get('payment_date', '')} · {format_money(float(item.get('amount', 0.0)))} · {item.get('payment_id', '')}": item for item in active_supplier}
            selected = options[st.selectbox("Pago", tuple(options.keys()))]
            reason = st.text_input("Motivo", key="supplier_payment_reversal_reason", max_chars=200)
            if st.button("Revertir pago a proveedor", type="primary", use_container_width=True):
                payment_id = str(selected.get("payment_id", ""))
                purchase_id = str(selected.get("purchase_id", ""))
                updated_payments = _mark_reversed(supplier_payments, payment_id, reason.strip())
                cash = _reverse_cash(cash, selected, "Ingreso", "Reverso de pago a proveedor", reason.strip() or f"Reverso de pago {payment_id}")
                updated_purchases: list[dict] = []
                for purchase in purchases:
                    current = dict(purchase)
                    if str(purchase.get("purchase_id", "")) == purchase_id:
                        paid = _active_paid(updated_payments, "purchase_id", purchase_id)
                        current["payment_status"] = _status(float(purchase.get("total", 0.0)), paid)
                        current["cash_registered"] = current["payment_status"] == "Pagado"
                    updated_purchases.append(current)
                st.session_state["supplier_payment_records"] = updated_payments
                st.session_state["purchases_registry"] = updated_purchases
                st.session_state["cash_movements"] = cash
                st.rerun()

    with team_tab:
        if not active_team:
            st.info("No hay pagos al equipo para revertir.")
        else:
            names = {str(item.get("member_id", "")): str(item.get("name", "Colaborador")) for item in members}
            options = {f"{names.get(str(item.get('member_id', '')), 'Colaborador')} · {format_money(float(item.get('amount', 0.0)))} · {item.get('payment_id', '')}": item for item in active_team}
            selected = options[st.selectbox("Pago al equipo", tuple(options.keys()))]
            reason = st.text_input("Motivo", key="team_payment_reversal_reason", max_chars=200)
            if st.button("Revertir pago al equipo", type="primary", use_container_width=True):
                payment_id = str(selected.get("payment_id", ""))
                updated_payments = _mark_reversed(team_payments, payment_id, reason.strip())
                cash = _reverse_cash(cash, selected, "Ingreso", "Reverso de pago al personal", reason.strip() or f"Reverso de pago {payment_id}")
                st.session_state["team_payments"] = updated_payments
                st.session_state["cash_movements"] = cash
                st.rerun()

    with history_tab:
        reversed_records = [("Cliente", item) for item in customer_payments if _is_reversed(item)] + [("Proveedor", item) for item in supplier_payments if _is_reversed(item)] + [("Equipo", item) for item in team_payments if _is_reversed(item)]
        if not reversed_records:
            st.info("Todavía no hay pagos revertidos.")
        for kind, item in reversed(reversed_records):
            with st.container(border=True):
                row = st.columns([3, 1])
                row[0].markdown(f"### {kind} · {item.get('payment_id', '')}")
                row[0].caption(f"{item.get('reversed_at_utc', '')} · {item.get('reversal_reason') or 'Sin motivo'}")
                row[1].metric("Monto", format_money(float(item.get("amount", 0.0))))

    render_info_card("Trazabilidad", "El pago original permanece registrado y el reverso se refleja como un movimiento opuesto en Caja.", "CONTROL DE PAGOS")
