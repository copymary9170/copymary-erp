"""Riesgo, acuerdos de pago y proyección de cobranza."""

from collections import defaultdict
from datetime import date, timedelta
from uuid import uuid4

import streamlit as st

from src import accounts_receivable_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    section = "payment_agreements"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Acuerdos de pago"
        session_backup.SESSION_KEYS = (
            "general_settings",
            *session_backup.LIST_SECTIONS,
            *session_backup.DICT_SECTIONS,
        )


_activate_backup()


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


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _paid(sale: dict, payments: list[dict]) -> float:
    sale_id = str(sale.get("sale_id", ""))
    total = _num(sale.get("total"))
    paid = sum(
        _num(item.get("amount"))
        for item in payments
        if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
    )
    if paid <= 0 and sale.get("payment_status") == "Pagado":
        paid = total
    return min(paid, total)


def _balance(sale: dict, payments: list[dict]) -> float:
    return max(_num(sale.get("total")) - _paid(sale, payments), 0.0)


def _meta(sale_id: str, metadata: list[dict]) -> dict:
    for item in metadata:
        if str(item.get("sale_id", "")) == sale_id:
            return dict(item)
    return {}


def _risk_score(sale: dict, payments: list[dict], metadata: list[dict], actions: list[dict]) -> tuple[int, str]:
    sale_id = str(sale.get("sale_id", ""))
    balance = _balance(sale, payments)
    meta = _meta(sale_id, metadata)
    due = _as_date(meta.get("due_date"))
    promise = _as_date(meta.get("promise_date"))
    days_overdue = max((date.today() - due).days, 0) if due else 0
    contacts = [item for item in actions if str(item.get("sale_id", "")) == sale_id]
    score = 0
    score += min(days_overdue * 2, 50)
    score += 20 if promise and promise < date.today() else 0
    score += 15 if balance >= 100 else 8 if balance >= 50 else 0
    score += 10 if contacts and str(contacts[-1].get("result", "")) in {"Sin respuesta", "Reclamo"} else 0
    if score >= 60:
        return score, "Crítico"
    if score >= 35:
        return score, "Alto"
    if score >= 15:
        return score, "Medio"
    return score, "Bajo"


def render_accounts_receivable_risk() -> None:
    render_page_header(
        "Cuentas por cobrar",
        "Prioriza riesgos, formaliza acuerdos y proyecta cuánto dinero puede entrar en los próximos días.",
    )
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_accounts_receivable_plus()
    finally:
        base.render_page_header = original_header

    sales = [sale for sale in _rows("sales_registry") if sale.get("order_status") != "Cancelado"]
    clients = _rows("customers_registry")
    payments = _rows("payment_records")
    metadata = _rows("receivables_registry")
    actions = _rows("collection_actions")
    agreements = _rows("payment_agreements")

    pending = [sale for sale in sales if _balance(sale, payments) > 0]
    ranked = sorted(
        [(sale, *_risk_score(sale, payments, metadata, actions)) for sale in pending],
        key=lambda item: item[1],
        reverse=True,
    )

    st.divider()
    st.markdown("### Riesgo de cartera")
    risk_totals: dict[str, float] = defaultdict(float)
    for sale, _, level in ranked:
        risk_totals[level] += _balance(sale, payments)
    columns = st.columns(4)
    for index, level in enumerate(("Crítico", "Alto", "Medio", "Bajo")):
        columns[index].metric(level, format_money(risk_totals[level]))

    st.markdown("### Cuentas prioritarias")
    for sale, score, level in ranked[:8]:
        sale_id = str(sale.get("sale_id", ""))
        with st.container(border=True):
            cols = st.columns([3, 1, 1, 1])
            cols[0].markdown(f"**{_client_name(str(sale.get('client_id', '')), clients)} · {sale.get('description', 'Venta')}**")
            cols[0].caption(f"ID {sale_id}")
            cols[1].metric("Saldo", format_money(_balance(sale, payments)))
            cols[2].metric("Riesgo", level)
            cols[3].metric("Puntaje", str(score))

    st.markdown("### Acuerdos de pago")
    options = {
        f"{_client_name(str(sale.get('client_id', '')), clients)} · {sale.get('description', 'Venta')} · {format_money(_balance(sale, payments))}": sale
        for sale in pending
    }
    if options:
        with st.form("payment_agreement_form", clear_on_submit=True):
            selected = st.selectbox("Cuenta", tuple(options.keys()))
            sale = options[selected]
            balance = _balance(sale, payments)
            cols = st.columns(3)
            installments = cols[0].number_input("Número de cuotas", min_value=1, max_value=24, value=2, step=1)
            first_due = cols[1].date_input("Primera fecha", value=date.today() + timedelta(days=7))
            frequency = cols[2].selectbox("Frecuencia", ("Semanal", "Quincenal", "Mensual"))
            note = st.text_input("Condiciones o nota")
            submitted = st.form_submit_button("Crear acuerdo", type="primary", use_container_width=True)
        if submitted:
            step_days = 7 if frequency == "Semanal" else 15 if frequency == "Quincenal" else 30
            amount = balance / int(installments)
            schedule = [
                {"installment": index + 1, "due_date": (first_due + timedelta(days=step_days * index)).isoformat(), "amount": amount, "status": "Pendiente"}
                for index in range(int(installments))
            ]
            agreements.append({
                "agreement_id": uuid4().hex[:12],
                "sale_id": str(sale.get("sale_id", "")),
                "created_at_utc": _now(),
                "total_agreed": balance,
                "frequency": frequency,
                "note": note.strip(),
                "status": "Activo",
                "schedule": schedule,
            })
            _save("payment_agreements", agreements)
            st.rerun()

    active_agreements = [item for item in agreements if item.get("status") == "Activo"]
    for agreement in active_agreements:
        sale = next((item for item in sales if str(item.get("sale_id", "")) == str(agreement.get("sale_id", ""))), {})
        with st.container(border=True):
            st.markdown(f"#### {_client_name(str(sale.get('client_id', '')), clients)}")
            st.caption(f"Acuerdo {agreement.get('agreement_id', '')} · {agreement.get('frequency', '')}")
            for installment in agreement.get("schedule", []):
                st.write(f"Cuota {installment.get('installment')}: {installment.get('due_date')} · {format_money(_num(installment.get('amount')))} · {installment.get('status', 'Pendiente')}")

    st.markdown("### Proyección de cobros")
    forecast = {7: 0.0, 15: 0.0, 30: 0.0}
    today = date.today()
    for agreement in active_agreements:
        for installment in agreement.get("schedule", []):
            due = _as_date(installment.get("due_date"))
            if not due or installment.get("status") == "Pagada":
                continue
            days = (due - today).days
            for horizon in forecast:
                if 0 <= days <= horizon:
                    forecast[horizon] += _num(installment.get("amount"))
    forecast_cols = st.columns(3)
    forecast_cols[0].metric("Próximos 7 días", format_money(forecast[7]))
    forecast_cols[1].metric("Próximos 15 días", format_money(forecast[15]))
    forecast_cols[2].metric("Próximos 30 días", format_money(forecast[30]))

    render_info_card(
        "Cobranza priorizada",
        "El riesgo, los acuerdos y la proyección se recalculan con los pagos y fechas disponibles.",
        "RIESGO Y RECUPERACIÓN",
    )
