"""Gestión ampliada de cuentas por cobrar para CopyMary ERP."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import csv
import io

import streamlit as st

from src import accounts_receivable as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money


def _activate_backup() -> None:
    section = "collection_actions"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Gestiones de cobranza"
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _payments_for(sale_id: str, payments: list[dict]) -> list[dict]:
    return [
        item for item in payments
        if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
    ]


def _paid(sale: dict, payments: list[dict]) -> float:
    total = _num(sale.get("total"))
    registered = sum(_num(item.get("amount")) for item in _payments_for(str(sale.get("sale_id", "")), payments))
    if registered > 0:
        return min(registered, total)
    return total if sale.get("payment_status") == "Pagado" else 0.0


def _balance(sale: dict, payments: list[dict]) -> float:
    return max(_num(sale.get("total")) - _paid(sale, payments), 0.0)


def _meta_for(sale_id: str, metadata: list[dict]) -> dict:
    for item in metadata:
        if str(item.get("sale_id", "")) == sale_id:
            return dict(item)
    return {"sale_id": sale_id, "due_date": "", "notes": ""}


def _aging_bucket(due_date: date | None, today: date) -> str:
    if not due_date or due_date >= today:
        return "Al día"
    days = (today - due_date).days
    if days <= 7:
        return "1–7 días"
    if days <= 15:
        return "8–15 días"
    if days <= 30:
        return "16–30 días"
    return "Más de 30 días"


def _export(sales: list[dict], clients: list[dict], payments: list[dict], metadata: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Venta", "Cliente", "Total", "Pagado", "Saldo", "Vencimiento", "Antigüedad", "Promesa", "Responsable"])
    today = date.today()
    for sale in sales:
        sale_id = str(sale.get("sale_id", ""))
        balance = _balance(sale, payments)
        if balance <= 0 or sale.get("order_status") == "Cancelado":
            continue
        meta = _meta_for(sale_id, metadata)
        due = _as_date(meta.get("due_date"))
        writer.writerow([
            sale_id,
            _client_name(str(sale.get("client_id", "")), clients),
            _num(sale.get("total")),
            _paid(sale, payments),
            balance,
            due.isoformat() if due else "",
            _aging_bucket(due, today),
            meta.get("promise_date", ""),
            meta.get("collection_owner", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def _update_meta(sale_id: str, updates: dict) -> None:
    metadata = _rows("receivables_registry")
    found = False
    changed = []
    for item in metadata:
        current = dict(item)
        if str(current.get("sale_id", "")) == sale_id:
            current.update(updates)
            current["updated_at_utc"] = _now()
            found = True
        changed.append(current)
    if not found:
        changed.append({"sale_id": sale_id, **updates, "updated_at_utc": _now()})
    _save("receivables_registry", changed)


def render_accounts_receivable_plus() -> None:
    render_page_header(
        "Cuentas por cobrar",
        "Controla antigüedad, compromisos de pago y acciones de cobranza para recuperar dinero a tiempo.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_accounts_receivable()
    finally:
        base.render_page_header = original_header

    sales = [sale for sale in _rows("sales_registry") if sale.get("order_status") != "Cancelado"]
    clients = _rows("customers_registry")
    payments = _rows("payment_records")
    metadata = _rows("receivables_registry")
    actions = _rows("collection_actions")
    today = date.today()

    pending = []
    for sale in sales:
        balance = _balance(sale, payments)
        if balance <= 0:
            continue
        sale_id = str(sale.get("sale_id", ""))
        meta = _meta_for(sale_id, metadata)
        due = _as_date(meta.get("due_date"))
        pending.append((sale, meta, balance, due, _aging_bucket(due, today)))

    st.divider()
    st.markdown("### Antigüedad de saldos")
    aging_totals: dict[str, float] = defaultdict(float)
    aging_counts: Counter[str] = Counter()
    for _, _, balance, _, bucket in pending:
        aging_totals[bucket] += balance
        aging_counts[bucket] += 1

    buckets = ("Al día", "1–7 días", "8–15 días", "16–30 días", "Más de 30 días")
    columns = st.columns(5)
    for index, bucket in enumerate(buckets):
        columns[index].metric(bucket, format_money(aging_totals[bucket]), f"{aging_counts[bucket]} cuenta(s)")

    overdue_total = sum(balance for _, _, balance, due, _ in pending if due and due < today)
    promises_today = [item for item in pending if _as_date(item[1].get("promise_date")) == today]
    broken_promises = [item for item in pending if _as_date(item[1].get("promise_date")) and _as_date(item[1].get("promise_date")) < today]
    collection_rate = (
        sum(_paid(sale, payments) for sale in sales) /
        max(sum(_num(sale.get("total")) for sale in sales), 1.0) * 100
    )

    summary = st.columns(4)
    summary[0].metric("Vencido total", format_money(overdue_total))
    summary[1].metric("Promesas para hoy", str(len(promises_today)))
    summary[2].metric("Promesas incumplidas", str(len(broken_promises)))
    summary[3].metric("Tasa de cobro", f"{collection_rate:,.1f}%")

    if broken_promises:
        st.error(f"Hay {len(broken_promises)} promesa(s) de pago vencida(s).")
    elif promises_today:
        st.warning(f"Hay {len(promises_today)} promesa(s) de pago para hoy.")

    if pending:
        st.download_button(
            "Descargar cartera por cobrar CSV",
            data=_export(sales, clients, payments, metadata),
            file_name=f"cuentas_por_cobrar_{today.isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    options = {
        f"{_client_name(str(sale.get('client_id', '')), clients)} · {sale.get('description', 'Venta')} · {format_money(balance)}": str(sale.get("sale_id", ""))
        for sale, _, balance, _, _ in pending
    }

    st.markdown("### Gestión de cobranza")
    if not options:
        st.success("No hay cuentas pendientes para gestionar.")
        return

    selected = st.selectbox("Cuenta", tuple(options.keys()), key="receivable_plus_account")
    sale_id = options[selected]
    sale, meta, balance, due_date, bucket = next(item for item in pending if str(item[0].get("sale_id", "")) == sale_id)

    profile_tab, action_tab, agenda_tab, history_tab = st.tabs(("Plan de cobro", "Registrar gestión", "Agenda", "Historial"))

    with profile_tab:
        with st.form("receivable_plan_form"):
            first = st.columns(3)
            due_input = first[0].date_input("Vencimiento", value=due_date or today)
            promise_input = first[1].date_input("Promesa de pago", value=_as_date(meta.get("promise_date")) or today)
            owner = first[2].text_input("Responsable", value=str(meta.get("collection_owner", "")))
            second = st.columns(2)
            priority = second[0].selectbox(
                "Prioridad",
                ("Baja", "Normal", "Alta", "Crítica"),
                index=("Baja", "Normal", "Alta", "Crítica").index(str(meta.get("collection_priority", "Normal"))) if str(meta.get("collection_priority", "Normal")) in ("Baja", "Normal", "Alta", "Crítica") else 1,
            )
            next_action = second[1].text_input("Próxima acción", value=str(meta.get("next_action", "")))
            notes = st.text_area("Notas de cobranza", value=str(meta.get("notes", "")), max_chars=500)
            save_plan = st.form_submit_button("Guardar plan de cobro", type="primary", use_container_width=True)
        if save_plan:
            _update_meta(sale_id, {
                "due_date": due_input.isoformat(),
                "promise_date": promise_input.isoformat(),
                "collection_owner": owner.strip(),
                "collection_priority": priority,
                "next_action": next_action.strip(),
                "notes": notes.strip(),
            })
            st.rerun()

        cards = st.columns(4)
        cards[0].metric("Saldo", format_money(balance))
        cards[1].metric("Antigüedad", bucket)
        cards[2].metric("Prioridad", str(meta.get("collection_priority", "Normal")))
        cards[3].metric("Responsable", str(meta.get("collection_owner") or "Sin asignar"))

    with action_tab:
        with st.form("collection_action_form", clear_on_submit=True):
            columns = st.columns(3)
            channel = columns[0].selectbox("Canal", ("WhatsApp", "Llamada", "Correo", "Presencial", "Otro"))
            result = columns[1].selectbox("Resultado", ("Prometió pagar", "Pago parcial", "Sin respuesta", "Solicitó prórroga", "Reclamo", "Otro"))
            responsible = columns[2].text_input("Responsable", value=str(meta.get("collection_owner", "")))
            note = st.text_area("Detalle", max_chars=700)
            next_date = st.date_input("Próximo contacto", value=today + timedelta(days=1))
            submitted = st.form_submit_button("Registrar gestión", type="primary", use_container_width=True)
        if submitted:
            if not note.strip():
                st.error("Escribe el detalle de la gestión.")
            else:
                actions.append({
                    "action_id": f"ca-{len(actions) + 1}-{sale_id}",
                    "sale_id": sale_id,
                    "created_at_utc": _now(),
                    "channel": channel,
                    "result": result,
                    "responsible": responsible.strip() or "Sin asignar",
                    "note": note.strip(),
                    "next_contact_date": next_date.isoformat(),
                })
                _save("collection_actions", actions)
                _update_meta(sale_id, {"next_contact_date": next_date.isoformat(), "last_collection_result": result})
                st.rerun()

    with agenda_tab:
        agenda = []
        for current_sale, current_meta, current_balance, _, current_bucket in pending:
            next_date = _as_date(current_meta.get("next_contact_date") or current_meta.get("promise_date"))
            if next_date:
                agenda.append((next_date, current_sale, current_meta, current_balance, current_bucket))
        agenda.sort(key=lambda item: item[0])
        if not agenda:
            st.info("No hay acciones de cobranza programadas.")
        for next_date, current_sale, current_meta, current_balance, current_bucket in agenda:
            with st.container(border=True):
                columns = st.columns([3, 1, 1, 1])
                columns[0].markdown(f"#### {_client_name(str(current_sale.get('client_id', '')), clients)}")
                columns[0].caption(str(current_meta.get("next_action") or current_meta.get("last_collection_result") or "Seguimiento pendiente"))
                columns[1].metric("Fecha", next_date.isoformat())
                columns[2].metric("Saldo", format_money(current_balance))
                columns[3].metric("Antigüedad", current_bucket)

    with history_tab:
        history = [item for item in actions if str(item.get("sale_id", "")) == sale_id]
        if not history:
            st.info("Esta cuenta todavía no tiene gestiones registradas.")
        for item in reversed(history):
            with st.container(border=True):
                st.markdown(f"**{item.get('channel', 'Contacto')} · {item.get('result', '')}**")
                st.write(str(item.get("note", "")))
                st.caption(f"{item.get('created_at_utc', '')} · {item.get('responsible', 'Sin asignar')} · Próximo contacto: {item.get('next_contact_date', '')}")

    render_info_card(
        "Cobranza trazable",
        "Promesas, responsables y gestiones quedan incluidas en el respaldo general.",
        "CUENTAS POR COBRAR",
    )
