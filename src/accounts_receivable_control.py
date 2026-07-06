"""Control avanzado de acuerdos, cuotas, crédito y recuperación de cartera."""

from collections import defaultdict
from datetime import date, datetime, timezone

import streamlit as st

from src import accounts_receivable_risk as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money


def _activate_backup() -> None:
    for section, label in (
        ("credit_policies", "Políticas de crédito"),
        ("agreement_events", "Historial de acuerdos de pago"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = (
        "general_settings",
        *session_backup.LIST_SECTIONS,
        *session_backup.DICT_SECTIONS,
    )


_activate_backup()


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, rows: list[dict]) -> None:
    st.session_state[key] = rows


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _sale_balance(sale: dict, payments: list[dict]) -> float:
    sale_id = str(sale.get("sale_id", ""))
    total = _num(sale.get("total"))
    paid = sum(
        _num(item.get("amount"))
        for item in payments
        if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
    )
    if paid <= 0 and sale.get("payment_status") == "Pagado":
        paid = total
    return max(total - min(paid, total), 0.0)


def _update_agreement(agreement_id: str, updates: dict) -> None:
    agreements = _rows("payment_agreements")
    for agreement in agreements:
        if str(agreement.get("agreement_id", "")) == agreement_id:
            agreement.update(updates)
            agreement["updated_at_utc"] = _now()
    _save("payment_agreements", agreements)


def _add_event(agreement_id: str, event_type: str, note: str) -> None:
    events = _rows("agreement_events")
    events.append({
        "agreement_id": agreement_id,
        "event_type": event_type,
        "note": note.strip(),
        "created_at_utc": _now(),
    })
    _save("agreement_events", events)


def render_accounts_receivable_control() -> None:
    render_page_header(
        "Cuentas por cobrar",
        "Controla cuotas, acuerdos vencidos, límites de crédito y recuperación real de cartera.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_accounts_receivable_risk()
    finally:
        base.render_page_header = original_header

    sales = [sale for sale in _rows("sales_registry") if sale.get("order_status") != "Cancelado"]
    clients = _rows("customers_registry")
    payments = _rows("payment_records")
    agreements = _rows("payment_agreements")
    policies = _rows("credit_policies")
    events = _rows("agreement_events")
    today = date.today()

    active_agreements = [item for item in agreements if item.get("status") == "Activo"]
    overdue_installments = []
    paid_installments = 0
    total_installments = 0
    for agreement in active_agreements:
        for installment in agreement.get("schedule", []):
            total_installments += 1
            if installment.get("status") == "Pagada":
                paid_installments += 1
                continue
            due = _as_date(installment.get("due_date"))
            if due and due < today:
                overdue_installments.append((agreement, installment))

    st.divider()
    st.markdown("### Control de acuerdos")
    metrics = st.columns(4)
    metrics[0].metric("Acuerdos activos", str(len(active_agreements)))
    metrics[1].metric("Cuotas vencidas", str(len(overdue_installments)))
    metrics[2].metric("Cuotas pagadas", str(paid_installments))
    metrics[3].metric(
        "Cumplimiento",
        f"{paid_installments / total_installments * 100:,.1f}%" if total_installments else "0.0%",
    )

    if overdue_installments:
        st.error(f"Hay {len(overdue_installments)} cuota(s) vencida(s) en acuerdos activos.")

    agreement_options = {
        f"{agreement.get('agreement_id', '')} · {agreement.get('frequency', '')}": str(agreement.get("agreement_id", ""))
        for agreement in active_agreements
    }

    payment_tab, renegotiation_tab, credit_tab, recovery_tab = st.tabs(
        ("Cuotas", "Renegociación", "Límites de crédito", "Recuperación")
    )

    with payment_tab:
        if not agreement_options:
            st.info("No hay acuerdos activos.")
        else:
            selected = st.selectbox("Acuerdo", tuple(agreement_options.keys()), key="agreement_control_selected")
            agreement_id = agreement_options[selected]
            agreement = next(item for item in active_agreements if str(item.get("agreement_id", "")) == agreement_id)
            sale = next((item for item in sales if str(item.get("sale_id", "")) == str(agreement.get("sale_id", ""))), {})
            st.caption(
                f"Cliente: {_client_name(str(sale.get('client_id', '')), clients)} · "
                f"Saldo actual: {format_money(_sale_balance(sale, payments))}"
            )
            schedule = [dict(item) for item in agreement.get("schedule", []) if isinstance(item, dict)]
            for installment in schedule:
                number = int(_num(installment.get("installment"), 0))
                due = _as_date(installment.get("due_date"))
                status = str(installment.get("status", "Pendiente"))
                is_overdue = bool(status != "Pagada" and due and due < today)
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1])
                    cols[0].markdown(f"**Cuota {number}**")
                    cols[0].caption(f"Vence: {installment.get('due_date', '')}")
                    cols[1].metric("Monto", format_money(_num(installment.get("amount"))))
                    cols[2].metric("Estado", "Vencida" if is_overdue else status)
                    if cols[3].button(
                        "Marcar pagada",
                        key=f"pay_installment_{agreement_id}_{number}",
                        use_container_width=True,
                        disabled=status == "Pagada",
                    ):
                        updated_schedule = []
                        for current in schedule:
                            row = dict(current)
                            if int(_num(row.get("installment"), 0)) == number:
                                row["status"] = "Pagada"
                                row["paid_at_utc"] = _now()
                            updated_schedule.append(row)
                        all_paid = all(item.get("status") == "Pagada" for item in updated_schedule)
                        _update_agreement(
                            agreement_id,
                            {"schedule": updated_schedule, "status": "Completado" if all_paid else "Activo"},
                        )
                        _add_event(agreement_id, "Cuota pagada", f"Cuota {number} marcada como pagada.")
                        st.rerun()

    with renegotiation_tab:
        if not agreement_options:
            st.info("No hay acuerdos activos para renegociar.")
        else:
            with st.form("renegotiate_agreement_form"):
                selected = st.selectbox("Acuerdo", tuple(agreement_options.keys()), key="renegotiate_selected")
                reason = st.text_area("Motivo de renegociación", max_chars=500)
                new_note = st.text_input("Nueva condición")
                submit = st.form_submit_button("Registrar renegociación", use_container_width=True)
            if submit:
                if not reason.strip():
                    st.error("Indica el motivo de la renegociación.")
                else:
                    agreement_id = agreement_options[selected]
                    _update_agreement(
                        agreement_id,
                        {
                            "renegotiated": True,
                            "renegotiation_reason": reason.strip(),
                            "renegotiation_note": new_note.strip(),
                            "renegotiated_at_utc": _now(),
                        },
                    )
                    _add_event(agreement_id, "Renegociación", reason)
                    st.rerun()

    with credit_tab:
        client_options = {
            f"{client.get('name', 'Cliente')} · {client.get('client_id', '')}": str(client.get("client_id", ""))
            for client in clients
        }
        if not client_options:
            st.info("No hay clientes registrados.")
        else:
            selected_client = st.selectbox("Cliente", tuple(client_options.keys()), key="credit_client")
            client_id = client_options[selected_client]
            current = next((item for item in policies if str(item.get("client_id", "")) == client_id), {})
            client_balance = sum(
                _sale_balance(sale, payments)
                for sale in sales
                if str(sale.get("client_id", "")) == client_id
            )
            with st.form("credit_policy_form"):
                cols = st.columns(3)
                credit_limit = cols[0].number_input("Límite de crédito", min_value=0.0, value=_num(current.get("credit_limit"), 0.0), step=5.0)
                max_days = cols[1].number_input("Días máximos", min_value=0, value=int(_num(current.get("max_credit_days"), 0)), step=1)
                blocked = cols[2].checkbox("Bloquear nuevas ventas a crédito", value=bool(current.get("blocked")))
                note = st.text_input("Observación", value=str(current.get("note", "")))
                save_policy = st.form_submit_button("Guardar política", type="primary", use_container_width=True)
            if save_policy:
                updated = [item for item in policies if str(item.get("client_id", "")) != client_id]
                updated.append({
                    "client_id": client_id,
                    "credit_limit": float(credit_limit),
                    "max_credit_days": int(max_days),
                    "blocked": bool(blocked),
                    "note": note.strip(),
                    "updated_at_utc": _now(),
                })
                _save("credit_policies", updated)
                st.rerun()
            st.metric("Saldo actual del cliente", format_money(client_balance))
            if credit_limit > 0 and client_balance > credit_limit:
                st.error("El cliente supera el límite de crédito configurado.")

    with recovery_tab:
        total_billed = sum(_num(sale.get("total")) for sale in sales)
        total_paid = total_billed - sum(_sale_balance(sale, payments) for sale in sales)
        recovery_rate = total_paid / total_billed * 100 if total_billed else 0.0
        recovered_by_client: dict[str, float] = defaultdict(float)
        for sale in sales:
            client_id = str(sale.get("client_id", ""))
            recovered_by_client[client_id] += _num(sale.get("total")) - _sale_balance(sale, payments)
        cards = st.columns(3)
        cards[0].metric("Facturado", format_money(total_billed))
        cards[1].metric("Recuperado", format_money(total_paid))
        cards[2].metric("Recuperación real", f"{recovery_rate:,.1f}%")
        for client_id, amount in sorted(recovered_by_client.items(), key=lambda item: item[1], reverse=True)[:10]:
            st.write(f"**{_client_name(client_id, clients)}:** {format_money(amount)} recuperado")

        st.markdown("#### Historial de acuerdos")
        if not events:
            st.info("Todavía no hay movimientos de acuerdos registrados.")
        for event in reversed(events[-20:]):
            st.caption(
                f"{event.get('created_at_utc', '')} · Acuerdo {event.get('agreement_id', '')} · "
                f"{event.get('event_type', '')}: {event.get('note', '')}"
            )

    render_info_card(
        "Control preventivo",
        "Cuotas, límites de crédito y renegociaciones quedan incluidos en el respaldo general.",
        "CARTERA Y RECUPERACIÓN",
    )
