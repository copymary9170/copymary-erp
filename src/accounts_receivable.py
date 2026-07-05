"""Cuentas por cobrar y abonos temporales para CopyMary ERP."""

from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _records(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, items: list[dict]) -> None:
    st.session_state[key] = items


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _payments_for(sale_id: str, payments: list[dict]) -> list[dict]:
    return [item for item in payments if str(item.get("sale_id", "")) == sale_id]


def _paid(sale: dict, payments: list[dict]) -> float:
    total = float(sale.get("total", 0.0))
    registered = sum(float(item.get("amount", 0.0)) for item in _payments_for(str(sale.get("sale_id", "")), payments))
    if registered > 0:
        return min(registered, total)
    if sale.get("payment_status") == "Pagado" and sale.get("cash_registered"):
        return total
    return 0.0


def _balance(sale: dict, payments: list[dict]) -> float:
    return max(float(sale.get("total", 0.0)) - _paid(sale, payments), 0.0)


def _payment_status(total: float, paid: float) -> str:
    if paid <= 0:
        return "Pendiente"
    if paid + 0.0001 >= total:
        return "Pagado"
    return "Abono"


def _meta_for(sale_id: str, metadata: list[dict]) -> dict:
    for item in metadata:
        if str(item.get("sale_id", "")) == sale_id:
            return dict(item)
    return {"sale_id": sale_id, "due_date": "", "notes": ""}


def _save_meta(metadata: list[dict], sale_id: str, due_date: str, notes: str) -> list[dict]:
    result: list[dict] = []
    found = False
    for item in metadata:
        current = dict(item)
        if str(item.get("sale_id", "")) == sale_id:
            current.update({"due_date": due_date, "notes": notes})
            found = True
        result.append(current)
    if not found:
        result.append({"sale_id": sale_id, "due_date": due_date, "notes": notes})
    return result


def _overdue(meta: dict, balance: float) -> bool:
    if balance <= 0 or not meta.get("due_date"):
        return False
    try:
        return date.fromisoformat(str(meta.get("due_date"))) < date.today()
    except ValueError:
        return False


def render_accounts_receivable() -> None:
    with st.container(border=True):
        render_page_header(
            "Cuentas por cobrar",
            "Registra abonos, controla saldos y organiza el seguimiento de cobro.",
        )
        st.caption("Cada abono genera un ingreso en Caja y actualiza la venta.")

    sales = _records("sales_registry")
    clients = _records("customers_registry")
    payments = _records("payment_records")
    metadata = _records("receivables_registry")
    cash = _records("cash_movements")

    active_sales = [sale for sale in sales if sale.get("order_status") != "Cancelado"]
    pending_sales = [sale for sale in active_sales if _balance(sale, payments) > 0]
    billed = sum(float(sale.get("total", 0.0)) for sale in active_sales)
    collected = sum(_paid(sale, payments) for sale in active_sales)
    due = sum(_balance(sale, payments) for sale in pending_sales)
    overdue_count = sum(
        1 for sale in pending_sales
        if _overdue(_meta_for(str(sale.get("sale_id", "")), metadata), _balance(sale, payments))
    )

    metrics = st.columns(4)
    metrics[0].metric("Facturado", format_money(billed))
    metrics[1].metric("Cobrado", format_money(collected))
    metrics[2].metric("Por cobrar", format_money(due))
    metrics[3].metric("Vencidas", str(overdue_count))

    st.subheader("Registrar abono")
    if not pending_sales:
        st.success("No hay ventas con saldo pendiente.")
    else:
        options: dict[str, dict] = {}
        for sale in pending_sales:
            label = (
                f"{sale.get('description', 'Venta')} · "
                f"{_client_name(str(sale.get('client_id', '')), clients)} · "
                f"Saldo {format_money(_balance(sale, payments))}"
            )
            options[label] = sale

        with st.form("receivable_payment_form", clear_on_submit=True):
            selected_label = st.selectbox("Venta", tuple(options.keys()))
            selected_sale = options[selected_label]
            current_balance = _balance(selected_sale, payments)
            columns = st.columns(4)
            with columns[0]:
                amount = st.number_input(
                    "Monto",
                    min_value=0.01,
                    max_value=float(current_balance),
                    value=float(current_balance),
                    step=0.5,
                )
            with columns[1]:
                method = st.selectbox("Método", ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro"))
            with columns[2]:
                reference = st.text_input("Referencia", max_chars=80)
            with columns[3]:
                payment_date = st.date_input("Fecha", value=date.today())
            notes = st.text_input("Notas", max_chars=180)
            submitted = st.form_submit_button("Registrar abono", type="primary", use_container_width=True)

        if submitted:
            sale_id = str(selected_sale.get("sale_id", ""))
            payment_id = uuid4().hex[:10]
            payments.append(
                {
                    "payment_id": payment_id,
                    "created_at_utc": _now(),
                    "payment_date": payment_date.isoformat(),
                    "sale_id": sale_id,
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
                    "movement_type": "Ingreso",
                    "category": "Cobro de venta",
                    "amount": float(amount),
                    "payment_method": method,
                    "reference": payment_id,
                    "notes": f"Abono a venta {sale_id}",
                }
            )

            paid_after = _paid(selected_sale, payments)
            total = float(selected_sale.get("total", 0.0))
            updated_sales: list[dict] = []
            for sale in sales:
                updated = dict(sale)
                if str(sale.get("sale_id", "")) == sale_id:
                    status = _payment_status(total, paid_after)
                    updated["payment_status"] = status
                    updated["cash_registered"] = status == "Pagado"
                updated_sales.append(updated)

            _save("payment_records", payments)
            _save("cash_movements", cash)
            _save("sales_registry", updated_sales)
            st.success("Abono registrado y Caja actualizada.")
            st.rerun()

    st.divider()
    st.subheader("Saldos pendientes")
    if not pending_sales:
        st.info("No hay cuentas pendientes.")
    else:
        for sale in sorted(pending_sales, key=lambda item: _balance(item, payments), reverse=True):
            sale_id = str(sale.get("sale_id", ""))
            total = float(sale.get("total", 0.0))
            paid = _paid(sale, payments)
            balance = _balance(sale, payments)
            meta = _meta_for(sale_id, metadata)
            history = _payments_for(sale_id, payments)

            with st.container(border=True):
                st.markdown(f"### {sale.get('description', 'Venta')}")
                st.caption(f"{_client_name(str(sale.get('client_id', '')), clients)} · ID {sale_id}")
                columns = st.columns(5)
                columns[0].metric("Total", format_money(total))
                columns[1].metric("Pagado", format_money(paid))
                columns[2].metric("Saldo", format_money(balance))
                columns[3].metric("Abonos", str(len(history)))
                columns[4].metric("Estado", "VENCIDA" if _overdue(meta, balance) else _payment_status(total, paid).upper())

                with st.form(f"receivable_followup_{sale_id}"):
                    followup_columns = st.columns(2)
                    default_due = None
                    if meta.get("due_date"):
                        try:
                            default_due = date.fromisoformat(str(meta.get("due_date")))
                        except ValueError:
                            default_due = None
                    with followup_columns[0]:
                        due_date = st.date_input("Vencimiento", value=default_due, key=f"due_{sale_id}")
                    with followup_columns[1]:
                        followup_notes = st.text_input(
                            "Notas de cobro",
                            value=str(meta.get("notes", "")),
                            max_chars=220,
                            key=f"followup_{sale_id}",
                        )
                    save_followup = st.form_submit_button("Guardar seguimiento", use_container_width=True)

                if save_followup:
                    metadata = _save_meta(
                        metadata,
                        sale_id,
                        due_date.isoformat() if due_date else "",
                        followup_notes.strip(),
                    )
                    _save("receivables_registry", metadata)
                    st.rerun()

                if history:
                    st.markdown("**Abonos:**")
                    for payment in reversed(history):
                        st.write(
                            f"- {payment.get('payment_date', '')} · "
                            f"{format_money(float(payment.get('amount', 0.0)))} · "
                            f"{payment.get('payment_method', '')} · Ref. {payment.get('reference') or 'Sin referencia'}"
                        )

                render_info_card(
                    "Seguimiento",
                    f"Vencimiento: {meta.get('due_date') or 'No definido'}. Notas: {meta.get('notes') or 'Sin notas'}.",
                    "CUENTA POR COBRAR",
                )

    render_info_card(
        "Datos provisionales",
        "Incluye pagos y seguimiento en el Respaldo general antes de cerrar la sesión.",
        "CONTROL TEMPORAL",
    )
