"""Planes, aprobaciones y previsión para cuentas por pagar."""

from datetime import date, timedelta
from uuid import uuid4

import streamlit as st

from src import accounts_payable_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("payable_plans", "Planes de pago a proveedores"),
        ("payable_documents", "Documentos de cuentas por pagar"),
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
    return [item for item in payments if str(item.get("purchase_id", "")) == purchase_id and not item.get("reversed")]


def _balance(purchase: dict, payments: list[dict]) -> float:
    total = _num(purchase.get("total"))
    paid = sum(_num(item.get("amount")) for item in _payments_for(str(purchase.get("purchase_id", "")), payments))
    if paid <= 0 and purchase.get("payment_status") == "Pagado" and purchase.get("cash_registered"):
        paid = total
    return max(total - min(paid, total), 0.0)


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


def _active_plan(purchase_id: str, plans: list[dict]) -> dict:
    for plan in reversed(plans):
        if str(plan.get("purchase_id", "")) == purchase_id and str(plan.get("status", "Activo")) == "Activo":
            return dict(plan)
    return {}


def render_accounts_payable_control() -> None:
    render_page_header(
        "Cuentas por pagar",
        "Planifica cuotas, aprueba pagos y anticipa compromisos para proteger la liquidez.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_accounts_payable_plus()
    finally:
        base.render_page_header = original_header

    purchases = [item for item in _rows("purchases_registry") if item.get("receipt_status") != "Cancelada"]
    suppliers = _rows("suppliers_registry")
    payments = _rows("supplier_payment_records")
    metadata = _rows("payables_registry")
    plans = _rows("payable_plans")
    documents = _rows("payable_documents")
    pending = [item for item in purchases if _balance(item, payments) > 0]
    today = date.today()

    due_7 = due_15 = due_30 = 0.0
    promises_due = 0
    missing_documents = 0
    for purchase in pending:
        purchase_id = str(purchase.get("purchase_id", ""))
        meta = _meta(purchase_id, metadata)
        balance = _balance(purchase, payments)
        scheduled = _as_date(meta.get("scheduled_payment_date")) or _as_date(meta.get("due_date"))
        if scheduled:
            days = (scheduled - today).days
            if 0 <= days <= 7:
                due_7 += balance
            if 0 <= days <= 15:
                due_15 += balance
            if 0 <= days <= 30:
                due_30 += balance
        promise = _as_date(meta.get("promise_date"))
        if promise and promise <= today and balance > 0:
            promises_due += 1
        required = [doc for doc in documents if str(doc.get("purchase_id", "")) == purchase_id and doc.get("required")]
        if required and any(not doc.get("received") for doc in required):
            missing_documents += 1

    st.divider()
    st.markdown("### Control preventivo")
    metrics = st.columns(4)
    metrics[0].metric("Compromisos 7 días", format_money(due_7))
    metrics[1].metric("Compromisos 15 días", format_money(due_15))
    metrics[2].metric("Promesas vencidas", str(promises_due))
    metrics[3].metric("Expedientes incompletos", str(missing_documents))

    if promises_due:
        st.error(f"Hay {promises_due} promesa(s) de pago vencida(s).")
    if missing_documents:
        st.warning(f"Hay {missing_documents} cuenta(s) con documentos requeridos pendientes.")

    plan_tab, approval_tab, promise_tab, documents_tab, forecast_tab = st.tabs(
        ("Plan de cuotas", "Aprobaciones", "Promesas", "Documentos", "Previsión")
    )

    options = {
        f"{purchase.get('material_name', 'Compra')} · {_supplier_name(str(purchase.get('supplier_id', '')), suppliers)} · {format_money(_balance(purchase, payments))}": str(purchase.get("purchase_id", ""))
        for purchase in pending
    }

    with plan_tab:
        if not options:
            st.info("No hay cuentas pendientes.")
        else:
            selected = st.selectbox("Cuenta", tuple(options.keys()), key="payable_plan_selected")
            purchase_id = options[selected]
            purchase = next(item for item in pending if str(item.get("purchase_id", "")) == purchase_id)
            balance = _balance(purchase, payments)
            current_plan = _active_plan(purchase_id, plans)
            with st.form("payable_plan_form"):
                columns = st.columns(3)
                installments = columns[0].number_input("Número de cuotas", min_value=1, max_value=24, value=int(current_plan.get("installments", 2)), step=1)
                frequency = columns[1].selectbox("Frecuencia", ("Semanal", "Quincenal", "Mensual"))
                first_date = columns[2].date_input("Primera cuota", value=today + timedelta(days=7))
                note = st.text_area("Condiciones", value=str(current_plan.get("note", "")), max_chars=500)
                submitted = st.form_submit_button("Crear plan", type="primary", use_container_width=True)
            if submitted:
                if current_plan:
                    for plan in plans:
                        if plan.get("plan_id") == current_plan.get("plan_id"):
                            plan["status"] = "Reemplazado"
                            plan["closed_at_utc"] = _now()
                step_days = {"Semanal": 7, "Quincenal": 15, "Mensual": 30}[frequency]
                amount = balance / int(installments)
                schedule = [
                    {
                        "number": index + 1,
                        "due_date": (first_date + timedelta(days=step_days * index)).isoformat(),
                        "amount": amount,
                        "status": "Pendiente",
                    }
                    for index in range(int(installments))
                ]
                plans.append({
                    "plan_id": uuid4().hex[:12],
                    "purchase_id": purchase_id,
                    "created_at_utc": _now(),
                    "installments": int(installments),
                    "frequency": frequency,
                    "balance_at_creation": balance,
                    "schedule": schedule,
                    "note": note.strip(),
                    "status": "Activo",
                })
                _save("payable_plans", plans)
                st.rerun()

            active_plan = _active_plan(purchase_id, plans)
            if active_plan:
                for installment in active_plan.get("schedule", []):
                    st.write(
                        f"Cuota {installment.get('number')} · {installment.get('due_date')} · "
                        f"{format_money(_num(installment.get('amount')))} · {installment.get('status', 'Pendiente')}"
                    )

    with approval_tab:
        if not options:
            st.info("No hay cuentas pendientes.")
        else:
            selected = st.selectbox("Cuenta", tuple(options.keys()), key="payable_approval_selected")
            purchase_id = options[selected]
            meta = _meta(purchase_id, metadata)
            with st.form("payable_approval_form"):
                columns = st.columns(3)
                approval_status = columns[0].selectbox("Estado", ("Pendiente", "Aprobado", "Rechazado"), index=("Pendiente", "Aprobado", "Rechazado").index(str(meta.get("approval_status", "Pendiente"))) if str(meta.get("approval_status", "Pendiente")) in ("Pendiente", "Aprobado", "Rechazado") else 0)
                approved_by = columns[1].text_input("Revisado por", value=str(meta.get("approved_by", "")))
                approval_limit = columns[2].number_input("Monto autorizado", min_value=0.0, value=_num(meta.get("approval_limit")), step=1.0)
                approval_note = st.text_area("Motivo o condición", value=str(meta.get("approval_note", "")), max_chars=500)
                submitted = st.form_submit_button("Guardar aprobación", type="primary", use_container_width=True)
            if submitted:
                _update_meta(purchase_id, {
                    "approval_status": approval_status,
                    "approved_by": approved_by.strip(),
                    "approval_limit": float(approval_limit),
                    "approval_note": approval_note.strip(),
                    "approved_at_utc": _now() if approval_status == "Aprobado" else "",
                })
                st.rerun()

    with promise_tab:
        if not options:
            st.info("No hay cuentas pendientes.")
        else:
            selected = st.selectbox("Cuenta", tuple(options.keys()), key="payable_promise_selected")
            purchase_id = options[selected]
            meta = _meta(purchase_id, metadata)
            with st.form("payable_promise_form"):
                columns = st.columns(2)
                promise_date = columns[0].date_input("Fecha prometida", value=_as_date(meta.get("promise_date")) or today + timedelta(days=7))
                contacted_by = columns[1].text_input("Responsable", value=str(meta.get("promise_responsible", "")))
                promise_note = st.text_area("Acuerdo con el proveedor", value=str(meta.get("promise_note", "")), max_chars=500)
                submitted = st.form_submit_button("Guardar promesa", type="primary", use_container_width=True)
            if submitted:
                _update_meta(purchase_id, {
                    "promise_date": promise_date.isoformat(),
                    "promise_responsible": contacted_by.strip(),
                    "promise_note": promise_note.strip(),
                    "promise_recorded_at_utc": _now(),
                })
                st.rerun()

    with documents_tab:
        if not options:
            st.info("No hay cuentas pendientes.")
        else:
            selected = st.selectbox("Cuenta", tuple(options.keys()), key="payable_document_selected")
            purchase_id = options[selected]
            with st.form("payable_document_form", clear_on_submit=True):
                columns = st.columns(3)
                document_type = columns[0].selectbox("Documento", ("Factura", "Orden de compra", "Nota de entrega", "Comprobante bancario", "Retención", "Otro"))
                reference = columns[1].text_input("Referencia")
                required = columns[2].checkbox("Obligatorio", value=True)
                received = st.checkbox("Documento recibido")
                submitted = st.form_submit_button("Registrar documento", type="primary", use_container_width=True)
            if submitted:
                documents.append({
                    "document_id": uuid4().hex[:12],
                    "purchase_id": purchase_id,
                    "document_type": document_type,
                    "reference": reference.strip(),
                    "required": required,
                    "received": received,
                    "created_at_utc": _now(),
                })
                _save("payable_documents", documents)
                st.rerun()

            for document in [item for item in documents if str(item.get("purchase_id", "")) == purchase_id]:
                st.write(
                    f"**{document.get('document_type', 'Documento')}:** "
                    f"{document.get('reference') or 'Sin referencia'} · "
                    f"{'Recibido' if document.get('received') else 'Pendiente'}"
                )

    with forecast_tab:
        forecast = {7: 0.0, 15: 0.0, 30: 0.0}
        for purchase in pending:
            purchase_id = str(purchase.get("purchase_id", ""))
            meta = _meta(purchase_id, metadata)
            plan = _active_plan(purchase_id, plans)
            if plan:
                for installment in plan.get("schedule", []):
                    due = _as_date(installment.get("due_date"))
                    if not due or str(installment.get("status", "Pendiente")) == "Pagada":
                        continue
                    days = (due - today).days
                    for horizon in forecast:
                        if 0 <= days <= horizon:
                            forecast[horizon] += _num(installment.get("amount"))
            else:
                due = _as_date(meta.get("scheduled_payment_date")) or _as_date(meta.get("due_date"))
                if due:
                    days = (due - today).days
                    for horizon in forecast:
                        if 0 <= days <= horizon:
                            forecast[horizon] += _balance(purchase, payments)
        columns = st.columns(3)
        columns[0].metric("Salida prevista 7 días", format_money(forecast[7]))
        columns[1].metric("Salida prevista 15 días", format_money(forecast[15]))
        columns[2].metric("Salida prevista 30 días", format_money(forecast[30]))
        st.caption("La previsión usa fechas programadas y planes de cuotas activos.")

    render_info_card(
        "Disciplina de pago",
        "Planes, aprobaciones, promesas y documentos quedan incluidos en el respaldo general.",
        "CONTROL DE PROVEEDORES",
    )
