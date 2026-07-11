"""Cuentas por pagar y pagos a proveedores para CopyMary ERP."""

from datetime import date
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _records, save_list as _save


def _supplier_name(supplier_id: str, suppliers: list[dict]) -> str:
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")) == supplier_id:
            return str(supplier.get("name", "Proveedor"))
    return "Sin proveedor"


def _payments_for(purchase_id: str, payments: list[dict]) -> list[dict]:
    return [item for item in payments if str(item.get("purchase_id", "")) == purchase_id]


def _paid(purchase: dict, payments: list[dict]) -> float:
    total = float(purchase.get("total", 0.0))
    explicit = sum(float(item.get("amount", 0.0)) for item in _payments_for(str(purchase.get("purchase_id", "")), payments))
    if explicit > 0:
        return min(explicit, total)
    if purchase.get("payment_status") == "Pagado" and purchase.get("cash_registered"):
        return total
    return 0.0


def _balance(purchase: dict, payments: list[dict]) -> float:
    return max(float(purchase.get("total", 0.0)) - _paid(purchase, payments), 0.0)


def _status(total: float, paid: float) -> str:
    if paid <= 0:
        return "Pendiente"
    if paid + 0.0001 >= total:
        return "Pagado"
    return "Abono"


def _meta_for(purchase_id: str, metadata: list[dict]) -> dict:
    for item in metadata:
        if str(item.get("purchase_id", "")) == purchase_id:
            return dict(item)
    return {"purchase_id": purchase_id, "due_date": "", "notes": ""}


def _upsert_meta(metadata: list[dict], purchase_id: str, due_date: str, notes: str) -> list[dict]:
    result: list[dict] = []
    found = False
    for item in metadata:
        current = dict(item)
        if str(item.get("purchase_id", "")) == purchase_id:
            current.update({"due_date": due_date, "notes": notes})
            found = True
        result.append(current)
    if not found:
        result.append({"purchase_id": purchase_id, "due_date": due_date, "notes": notes})
    return result


def _is_overdue(meta: dict, balance: float) -> bool:
    if balance <= 0 or not meta.get("due_date"):
        return False
    try:
        return date.fromisoformat(str(meta.get("due_date"))) < date.today()
    except ValueError:
        return False


def render_accounts_payable() -> None:
    with st.container(border=True):
        render_page_header(
            "Cuentas por pagar",
            "Controla saldos pendientes, abonos y vencimientos de compras a proveedores.",
        )
        st.caption("Cada pago genera un egreso en Caja y actualiza el estado de la compra.")

    purchases = _records("purchases_registry")
    suppliers = _records("suppliers_registry")
    payments = _records("supplier_payment_records")
    metadata = _records("payables_registry")
    cash = _records("cash_movements")

    active = [item for item in purchases if item.get("receipt_status") != "Cancelada"]
    pending = [item for item in active if _balance(item, payments) > 0]
    total = sum(float(item.get("total", 0.0)) for item in active)
    paid = sum(_paid(item, payments) for item in active)
    due = sum(_balance(item, payments) for item in pending)
    overdue = sum(
        1
        for item in pending
        if _is_overdue(_meta_for(str(item.get("purchase_id", "")), metadata), _balance(item, payments))
    )

    metrics = st.columns(4)
    metrics[0].metric("Comprado", format_money(total))
    metrics[1].metric("Pagado", format_money(paid))
    metrics[2].metric("Por pagar", format_money(due))
    metrics[3].metric("Vencidas", str(overdue))

    st.subheader("Registrar pago")
    if not pending:
        st.success("No hay compras con saldo pendiente.")
    else:
        options: dict[str, dict] = {}
        for purchase in pending:
            label = (
                f"{purchase.get('material_name', 'Compra')} · "
                f"{_supplier_name(str(purchase.get('supplier_id', '')), suppliers)} · "
                f"Saldo {format_money(_balance(purchase, payments))}"
            )
            options[label] = purchase

        with st.form("supplier_payment_form", clear_on_submit=True):
            selected_label = st.selectbox("Compra", tuple(options.keys()))
            selected = options[selected_label]
            current_balance = _balance(selected, payments)
            row = st.columns(4)
            with row[0]:
                amount = st.number_input("Monto", min_value=0.01, max_value=float(current_balance), value=float(current_balance), step=0.5)
            with row[1]:
                method = st.selectbox("Método", ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro"))
            with row[2]:
                reference = st.text_input("Referencia", max_chars=80)
            with row[3]:
                payment_date = st.date_input("Fecha", value=date.today())
            notes = st.text_input("Notas", max_chars=180)
            submitted = st.form_submit_button("Registrar pago", type="primary", use_container_width=True)

        if submitted:
            purchase_id = str(selected.get("purchase_id", ""))
            payment_id = uuid4().hex[:10]
            payments.append(
                {
                    "payment_id": payment_id,
                    "created_at_utc": _now(),
                    "payment_date": payment_date.isoformat(),
                    "purchase_id": purchase_id,
                    "amount": float(amount),
                    "payment_method": method,
                    "reference": reference.strip(),
                    "notes": notes.strip(),
                }
            )
            cash.append(
                {
                    "movement_id": uuid4().hex[:10],
                    "created_at_utc": _now(),
                    "movement_type": "Egreso",
                    "category": "Pago a proveedor",
                    "amount": float(amount),
                    "payment_method": method,
                    "reference": payment_id,
                    "notes": f"Pago de compra {purchase_id}",
                }
            )

            paid_after = _paid(selected, payments)
            purchase_total = float(selected.get("total", 0.0))
            updated_purchases: list[dict] = []
            for purchase in purchases:
                updated = dict(purchase)
                if str(purchase.get("purchase_id", "")) == purchase_id:
                    status = _status(purchase_total, paid_after)
                    updated["payment_status"] = status
                    updated["cash_registered"] = status == "Pagado"
                updated_purchases.append(updated)

            _save("supplier_payment_records", payments)
            _save("cash_movements", cash)
            _save("purchases_registry", updated_purchases)
            st.success("Pago registrado y Caja actualizada.")
            st.rerun()

    st.divider()
    st.subheader("Saldos pendientes")
    if not pending:
        st.info("No hay cuentas pendientes.")
        return

    for purchase in sorted(pending, key=lambda item: _balance(item, payments), reverse=True):
        purchase_id = str(purchase.get("purchase_id", ""))
        purchase_total = float(purchase.get("total", 0.0))
        paid_amount = _paid(purchase, payments)
        balance = _balance(purchase, payments)
        meta = _meta_for(purchase_id, metadata)
        history = _payments_for(purchase_id, payments)

        with st.container(border=True):
            st.markdown(f"### {purchase.get('material_name', 'Compra')}")
            st.caption(f"{_supplier_name(str(purchase.get('supplier_id', '')), suppliers)} · ID {purchase_id}")
            row = st.columns(5)
            row[0].metric("Total", format_money(purchase_total))
            row[1].metric("Pagado", format_money(paid_amount))
            row[2].metric("Saldo", format_money(balance))
            row[3].metric("Pagos", str(len(history)))
            row[4].metric("Estado", "VENCIDA" if _is_overdue(meta, balance) else _status(purchase_total, paid_amount).upper())

            with st.form(f"payable_followup_{purchase_id}"):
                cols = st.columns(2)
                default_due = None
                if meta.get("due_date"):
                    try:
                        default_due = date.fromisoformat(str(meta.get("due_date")))
                    except ValueError:
                        default_due = None
                with cols[0]:
                    due_date = st.date_input("Vencimiento", value=default_due, key=f"payable_due_{purchase_id}")
                with cols[1]:
                    followup_notes = st.text_input("Notas", value=str(meta.get("notes", "")), max_chars=220, key=f"payable_notes_{purchase_id}")
                save_followup = st.form_submit_button("Guardar seguimiento", use_container_width=True)

            if save_followup:
                metadata = _upsert_meta(
                    metadata,
                    purchase_id,
                    due_date.isoformat() if due_date else "",
                    followup_notes.strip(),
                )
                _save("payables_registry", metadata)
                st.rerun()

            if history:
                st.markdown("**Pagos registrados:**")
                for payment in reversed(history):
                    st.write(
                        f"- {payment.get('payment_date', '')} · {format_money(float(payment.get('amount', 0.0)))} · "
                        f"{payment.get('payment_method', '')} · Ref. {payment.get('reference') or 'Sin referencia'}"
                    )

            render_info_card(
                "Seguimiento",
                f"Vencimiento: {meta.get('due_date') or 'No definido'}. Notas: {meta.get('notes') or 'Sin notas'}.",
                "CUENTA POR PAGAR",
            )
