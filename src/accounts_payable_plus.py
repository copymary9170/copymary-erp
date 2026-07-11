"""Gestión ampliada de cuentas por pagar para CopyMary ERP."""

from collections import defaultdict
from datetime import date, timedelta
import csv
import io

import streamlit as st

from src import accounts_payable as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    section = "payable_actions"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Acciones de cuentas por pagar"
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


def _supplier_name(supplier_id: str, suppliers: list[dict]) -> str:
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")) == supplier_id:
            return str(supplier.get("name", "Proveedor"))
    return "Sin proveedor"


def _payments_for(purchase_id: str, payments: list[dict]) -> list[dict]:
    return [
        item for item in payments
        if str(item.get("purchase_id", "")) == purchase_id and not item.get("reversed")
    ]


def _paid(purchase: dict, payments: list[dict]) -> float:
    total = _num(purchase.get("total"))
    explicit = sum(_num(item.get("amount")) for item in _payments_for(str(purchase.get("purchase_id", "")), payments))
    if explicit > 0:
        return min(explicit, total)
    if purchase.get("payment_status") == "Pagado" and purchase.get("cash_registered"):
        return total
    return 0.0


def _balance(purchase: dict, payments: list[dict]) -> float:
    return max(_num(purchase.get("total")) - _paid(purchase, payments), 0.0)


def _meta(purchase_id: str, metadata: list[dict]) -> dict:
    for item in metadata:
        if str(item.get("purchase_id", "")) == purchase_id:
            return dict(item)
    return {}


def _update_meta(purchase_id: str, updates: dict) -> None:
    metadata = _rows("payables_registry")
    changed = []
    found = False
    for item in metadata:
        row = dict(item)
        if str(row.get("purchase_id", "")) == purchase_id:
            row.update(updates)
            row["updated_at_utc"] = _now()
            found = True
        changed.append(row)
    if not found:
        changed.append({"purchase_id": purchase_id, **updates, "updated_at_utc": _now()})
    _save("payables_registry", changed)


def _add_action(purchase_id: str, action_type: str, note: str, responsible: str = "") -> None:
    actions = _rows("payable_actions")
    actions.append({
        "purchase_id": purchase_id,
        "action_type": action_type,
        "note": note.strip(),
        "responsible": responsible.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("payable_actions", actions)


def _aging_bucket(due_date: date | None, balance: float) -> str:
    if balance <= 0:
        return "Pagada"
    if not due_date or due_date >= date.today():
        return "Por vencer"
    days = (date.today() - due_date).days
    if days <= 7:
        return "1-7 días"
    if days <= 15:
        return "8-15 días"
    if days <= 30:
        return "16-30 días"
    return ">30 días"


def _export(purchases: list[dict], suppliers: list[dict], payments: list[dict], metadata: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Compra", "Proveedor", "Material", "Total", "Pagado", "Saldo", "Vencimiento",
        "Antigüedad", "Prioridad", "Pago programado", "Descuento por pronto pago",
    ])
    for purchase in purchases:
        purchase_id = str(purchase.get("purchase_id", ""))
        meta = _meta(purchase_id, metadata)
        balance = _balance(purchase, payments)
        due = _as_date(meta.get("due_date"))
        writer.writerow([
            purchase_id,
            _supplier_name(str(purchase.get("supplier_id", "")), suppliers),
            purchase.get("material_name", ""),
            _num(purchase.get("total")),
            _paid(purchase, payments),
            balance,
            meta.get("due_date", ""),
            _aging_bucket(due, balance),
            meta.get("priority", "Normal"),
            meta.get("scheduled_payment_date", ""),
            _num(meta.get("early_payment_discount")),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_accounts_payable_plus() -> None:
    render_page_header(
        "Cuentas por pagar",
        "Prioriza vencimientos, programa pagos y protege la liquidez frente a compromisos con proveedores.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_accounts_payable()
    finally:
        base.render_page_header = original_header

    purchases = [item for item in _rows("purchases_registry") if item.get("receipt_status") != "Cancelada"]
    suppliers = _rows("suppliers_registry")
    payments = _rows("supplier_payment_records")
    metadata = _rows("payables_registry")
    actions = _rows("payable_actions")
    pending = [item for item in purchases if _balance(item, payments) > 0]
    today = date.today()

    aging: dict[str, float] = defaultdict(float)
    upcoming_7 = 0.0
    upcoming_15 = 0.0
    upcoming_30 = 0.0
    supplier_exposure: dict[str, float] = defaultdict(float)
    for purchase in pending:
        purchase_id = str(purchase.get("purchase_id", ""))
        meta = _meta(purchase_id, metadata)
        balance = _balance(purchase, payments)
        due = _as_date(meta.get("due_date"))
        aging[_aging_bucket(due, balance)] += balance
        supplier_exposure[_supplier_name(str(purchase.get("supplier_id", "")), suppliers)] += balance
        if due:
            days = (due - today).days
            if 0 <= days <= 7:
                upcoming_7 += balance
            if 0 <= days <= 15:
                upcoming_15 += balance
            if 0 <= days <= 30:
                upcoming_30 += balance

    st.divider()
    st.markdown("### Antigüedad de saldos")
    aging_columns = st.columns(5)
    for index, bucket in enumerate(("Por vencer", "1-7 días", "8-15 días", "16-30 días", ">30 días")):
        aging_columns[index].metric(bucket, format_money(aging[bucket]))

    st.markdown("### Calendario de pagos")
    calendar_columns = st.columns(3)
    calendar_columns[0].metric("Próximos 7 días", format_money(upcoming_7))
    calendar_columns[1].metric("Próximos 15 días", format_money(upcoming_15))
    calendar_columns[2].metric("Próximos 30 días", format_money(upcoming_30))

    if aging[">30 días"] > 0:
        st.error(f"Hay {format_money(aging['>30 días'])} con más de 30 días de atraso.")

    planning_tab, priority_tab, suppliers_tab, history_tab, export_tab = st.tabs(
        ("Programación", "Prioridades", "Proveedores", "Historial", "Exportación")
    )

    options = {
        f"{purchase.get('material_name', 'Compra')} · {_supplier_name(str(purchase.get('supplier_id', '')), suppliers)} · {format_money(_balance(purchase, payments))}": str(purchase.get("purchase_id", ""))
        for purchase in pending
    }

    with planning_tab:
        if not options:
            st.info("No hay cuentas pendientes.")
        else:
            selected = st.selectbox("Cuenta", tuple(options.keys()), key="payable_schedule_selected")
            purchase_id = options[selected]
            purchase = next(item for item in pending if str(item.get("purchase_id", "")) == purchase_id)
            meta = _meta(purchase_id, metadata)
            with st.form("payable_schedule_form"):
                columns = st.columns(4)
                scheduled = columns[0].date_input("Fecha programada", value=_as_date(meta.get("scheduled_payment_date")) or today + timedelta(days=7))
                priority = columns[1].selectbox("Prioridad", ("Baja", "Normal", "Alta", "Urgente"), index=("Baja", "Normal", "Alta", "Urgente").index(str(meta.get("priority", "Normal"))) if str(meta.get("priority", "Normal")) in ("Baja", "Normal", "Alta", "Urgente") else 1)
                responsible = columns[2].text_input("Responsable", value=str(meta.get("responsible", "")))
                early_discount = columns[3].number_input("Descuento pronto pago %", min_value=0.0, max_value=100.0, value=_num(meta.get("early_payment_discount")), step=0.5)
                note = st.text_area("Nota de programación", value=str(meta.get("schedule_note", "")), max_chars=500)
                submitted = st.form_submit_button("Guardar programación", type="primary", use_container_width=True)
            if submitted:
                _update_meta(purchase_id, {
                    "scheduled_payment_date": scheduled.isoformat(),
                    "priority": priority,
                    "responsible": responsible.strip(),
                    "early_payment_discount": float(early_discount),
                    "schedule_note": note.strip(),
                })
                _add_action(purchase_id, "Pago programado", f"Fecha {scheduled.isoformat()} · Prioridad {priority}", responsible)
                st.rerun()

            balance = _balance(purchase, payments)
            saving = balance * float(early_discount) / 100
            cards = st.columns(3)
            cards[0].metric("Saldo", format_money(balance))
            cards[1].metric("Ahorro potencial", format_money(saving))
            cards[2].metric("Pago neto", format_money(max(balance - saving, 0.0)))

    with priority_tab:
        ranked = []
        priority_weight = {"Urgente": 4, "Alta": 3, "Normal": 2, "Baja": 1}
        for purchase in pending:
            purchase_id = str(purchase.get("purchase_id", ""))
            meta = _meta(purchase_id, metadata)
            due = _as_date(meta.get("due_date"))
            overdue_days = max((today - due).days, 0) if due else 0
            score = priority_weight.get(str(meta.get("priority", "Normal")), 2) * 20 + min(overdue_days, 30) + min(int(_balance(purchase, payments) / 10), 30)
            ranked.append((score, purchase, meta, overdue_days))
        for score, purchase, meta, overdue_days in sorted(ranked, key=lambda item: item[0], reverse=True):
            with st.container(border=True):
                columns = st.columns([3, 1, 1, 1])
                columns[0].markdown(f"**{purchase.get('material_name', 'Compra')} · {_supplier_name(str(purchase.get('supplier_id', '')), suppliers)}**")
                columns[0].caption(f"Vence: {meta.get('due_date') or 'Sin fecha'} · Responsable: {meta.get('responsible') or 'Sin asignar'}")
                columns[1].metric("Saldo", format_money(_balance(purchase, payments)))
                columns[2].metric("Prioridad", str(meta.get("priority", "Normal")))
                columns[3].metric("Puntaje", str(score))
                if overdue_days:
                    st.warning(f"Atraso: {overdue_days} día(s).")

    with suppliers_tab:
        total_due = sum(supplier_exposure.values())
        for supplier, amount in sorted(supplier_exposure.items(), key=lambda item: item[1], reverse=True):
            share = amount / total_due * 100 if total_due else 0.0
            with st.container(border=True):
                columns = st.columns([3, 1, 1])
                columns[0].markdown(f"**{supplier}**")
                columns[1].metric("Saldo", format_money(amount))
                columns[2].metric("Concentración", f"{share:,.1f}%")
                if share >= 40:
                    st.warning("Alta concentración de deuda con este proveedor.")

    with history_tab:
        selected_filter = st.selectbox("Filtrar", ("Todos", *[str(item.get("purchase_id", "")) for item in pending]), key="payable_action_filter")
        visible = actions if selected_filter == "Todos" else [item for item in actions if str(item.get("purchase_id", "")) == selected_filter]
        if not visible:
            st.info("No hay acciones registradas.")
        for action in reversed(visible[-100:]):
            with st.container(border=True):
                st.markdown(f"**{action.get('action_type', 'Acción')} · {action.get('purchase_id', '')}**")
                st.write(str(action.get("note", "")))
                st.caption(f"{action.get('created_at_utc', '')} · {action.get('responsible', 'Sin asignar')}")

    with export_tab:
        if purchases:
            st.download_button(
                "Descargar cuentas por pagar CSV",
                data=_export(purchases, suppliers, payments, metadata),
                file_name=f"cuentas_por_pagar_{today.isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("No hay compras registradas para exportar.")

    render_info_card(
        "Liquidez protegida",
        "La antigüedad, programación y prioridades se recalculan con saldos y vencimientos disponibles.",
        "CUENTAS POR PAGAR",
    )
