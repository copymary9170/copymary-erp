"""Control presupuestario, conciliación y reposición de compras."""

from datetime import date, datetime, timedelta
from uuid import uuid4

import streamlit as st

from src import purchases_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    section = "purchase_controls"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Controles de compras"
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


def _as_datetime(value) -> datetime | None:
    raw = str(value or "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.fromisoformat(raw[:10])
        except ValueError:
            return None


def _supplier_name(supplier_id: str, suppliers: list[dict]) -> str:
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")) == supplier_id:
            return str(supplier.get("name", "Proveedor"))
    return "Sin proveedor"


def _purchase_control(purchase_id: str, controls: list[dict]) -> dict:
    for item in controls:
        if str(item.get("purchase_id", "")) == purchase_id:
            return dict(item)
    return {}


def _update_control(purchase_id: str, updates: dict) -> None:
    controls = _rows("purchase_controls")
    changed = []
    found = False
    for item in controls:
        row = dict(item)
        if str(row.get("purchase_id", "")) == purchase_id:
            row.update(updates)
            row["updated_at_utc"] = _now()
            found = True
        changed.append(row)
    if not found:
        changed.append({"purchase_id": purchase_id, **updates, "updated_at_utc": _now()})
    _save("purchase_controls", changed)


def _duplicates(purchases: list[dict]) -> list[tuple[dict, dict]]:
    result = []
    for index, purchase in enumerate(purchases):
        created = _as_datetime(purchase.get("created_at_utc"))
        if not created:
            continue
        for other in purchases[index + 1:]:
            other_created = _as_datetime(other.get("created_at_utc"))
            if not other_created:
                continue
            same_supplier = str(purchase.get("supplier_id", "")) == str(other.get("supplier_id", ""))
            same_material = str(purchase.get("material_name", "")).strip().casefold() == str(other.get("material_name", "")).strip().casefold()
            same_total = abs(_num(purchase.get("total")) - _num(other.get("total"))) < 0.01
            close_dates = abs((created.date() - other_created.date()).days) <= 7
            if same_supplier and same_material and same_total and close_dates:
                result.append((purchase, other))
    return result


def render_purchases_control() -> None:
    render_page_header(
        "Compras",
        "Controla presupuesto, duplicados, recepción, pago y reposición antes de que generen pérdidas.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_purchases_plus()
    finally:
        base.render_page_header = original_header

    purchases = _rows("purchases_registry")
    requests = _rows("purchase_requests")
    suppliers = _rows("suppliers_registry")
    inventory = _rows("inventory_registry")
    controls = _rows("purchase_controls")

    duplicate_pairs = _duplicates(purchases)
    low_stock = [
        item for item in inventory
        if _num(item.get("minimum_stock")) > 0
        and _num(item.get("available_quantity", item.get("quantity"))) <= _num(item.get("minimum_stock"))
    ]
    mismatches = []
    over_budget = []
    for purchase in purchases:
        purchase_id = str(purchase.get("purchase_id", ""))
        control = _purchase_control(purchase_id, controls)
        ordered = _num(purchase.get("quantity"))
        received = _num(purchase.get("received_quantity"), ordered if purchase.get("receipt_status") == "Recibida" else 0.0)
        if purchase.get("receipt_status") == "Recibida" and received < ordered:
            mismatches.append(purchase)
        budget = _num(control.get("approved_budget"))
        if budget > 0 and _num(purchase.get("total")) > budget:
            over_budget.append(purchase)

    st.divider()
    st.markdown("### Alertas y control")
    metrics = st.columns(4)
    metrics[0].metric("Posibles duplicados", str(len(duplicate_pairs)))
    metrics[1].metric("Sobrecostos", str(len(over_budget)))
    metrics[2].metric("Diferencias", str(len(mismatches)))
    metrics[3].metric("Reposiciones sugeridas", str(len(low_stock)))

    if duplicate_pairs:
        st.error(f"Se detectaron {len(duplicate_pairs)} posible(s) compra(s) duplicada(s).")
    if over_budget:
        st.warning(f"Hay {len(over_budget)} compra(s) que superan el presupuesto aprobado.")

    budget_tab, reconcile_tab, duplicate_tab, replenishment_tab = st.tabs(
        ("Presupuesto", "Conciliación", "Duplicados", "Reposición")
    )

    purchase_options = {
        f"{item.get('material_name', 'Compra')} · {item.get('purchase_id', '')}": str(item.get("purchase_id", ""))
        for item in purchases
    }

    with budget_tab:
        if not purchase_options:
            st.info("No hay compras registradas.")
        else:
            selected = st.selectbox("Compra", tuple(purchase_options.keys()), key="purchase_budget_selected")
            purchase_id = purchase_options[selected]
            purchase = next(item for item in purchases if str(item.get("purchase_id", "")) == purchase_id)
            control = _purchase_control(purchase_id, controls)
            request_options = {"Sin solicitud vinculada": ""}
            for request in requests:
                request_options[f"{request.get('material_name', 'Solicitud')} · {request.get('request_id', '')}"] = str(request.get("request_id", ""))
            with st.form("purchase_budget_form"):
                columns = st.columns(3)
                approved_budget = columns[0].number_input("Presupuesto aprobado", min_value=0.0, value=_num(control.get("approved_budget")), step=1.0)
                selected_request = columns[1].selectbox("Solicitud vinculada", tuple(request_options.keys()))
                approver = columns[2].text_input("Aprobado por", value=str(control.get("approved_by", "")))
                note = st.text_area("Justificación o condición", value=str(control.get("budget_note", "")), max_chars=500)
                save_budget = st.form_submit_button("Guardar control presupuestario", type="primary", use_container_width=True)
            if save_budget:
                _update_control(purchase_id, {
                    "approved_budget": float(approved_budget),
                    "request_id": request_options[selected_request],
                    "approved_by": approver.strip(),
                    "budget_note": note.strip(),
                })
                st.rerun()

            actual = _num(purchase.get("total"))
            variance = actual - float(approved_budget)
            cards = st.columns(3)
            cards[0].metric("Costo real", format_money(actual))
            cards[1].metric("Presupuesto", format_money(float(approved_budget)))
            cards[2].metric("Variación", format_money(variance), "Sobrecosto" if variance > 0 else "Dentro del presupuesto")

    with reconcile_tab:
        if not purchase_options:
            st.info("No hay compras registradas.")
        else:
            selected = st.selectbox("Compra", tuple(purchase_options.keys()), key="purchase_reconcile_selected")
            purchase_id = purchase_options[selected]
            purchase = next(item for item in purchases if str(item.get("purchase_id", "")) == purchase_id)
            ordered = _num(purchase.get("quantity"))
            received = _num(purchase.get("received_quantity"), ordered if purchase.get("receipt_status") == "Recibida" else 0.0)
            paid = str(purchase.get("payment_status", "Pendiente")) == "Pagado"
            reception_ok = received >= ordered and str(purchase.get("receipt_status", "")) == "Recibida"
            invoice_ok = bool(str(purchase.get("order_reference", "")).strip())
            cards = st.columns(4)
            cards[0].metric("Pedido", f"{ordered:,.2f}")
            cards[1].metric("Recibido", f"{received:,.2f}")
            cards[2].metric("Pago", "Conciliado" if paid else "Pendiente")
            cards[3].metric("Referencia", "Completa" if invoice_ok else "Faltante")

            if reception_ok and paid and invoice_ok:
                st.success("La compra está conciliada: pedido, recepción y pago coinciden.")
            else:
                st.warning("La compra tiene diferencias o datos pendientes antes de considerarse conciliada.")

            with st.form("purchase_reconcile_form"):
                reviewed_by = st.text_input("Revisado por")
                reconciliation_note = st.text_area("Observación", max_chars=500)
                confirm = st.checkbox("Confirmo que revisé pedido, recepción y pago")
                save_review = st.form_submit_button("Guardar revisión", type="primary", use_container_width=True)
            if save_review:
                _update_control(purchase_id, {
                    "reconciliation_reviewed": bool(confirm),
                    "reconciliation_status": "Conciliada" if confirm and reception_ok and paid and invoice_ok else "Con diferencias",
                    "reconciliation_note": reconciliation_note.strip(),
                    "reviewed_by": reviewed_by.strip(),
                    "reviewed_at_utc": _now(),
                })
                st.rerun()

    with duplicate_tab:
        if not duplicate_pairs:
            st.success("No se detectaron compras potencialmente duplicadas.")
        for first, second in duplicate_pairs:
            with st.container(border=True):
                st.markdown(f"**{first.get('material_name', 'Compra')} · {_supplier_name(str(first.get('supplier_id', '')), suppliers)}**")
                st.write(
                    f"{first.get('purchase_id', '')} y {second.get('purchase_id', '')} · "
                    f"{format_money(_num(first.get('total')))} · fechas cercanas"
                )
                st.caption("Revisa antes de pagar o recibir nuevamente.")

    with replenishment_tab:
        if not low_stock:
            st.success("No hay materiales en nivel de reposición.")
        for item in low_stock:
            item_id = str(item.get("item_id", ""))
            available = _num(item.get("available_quantity", item.get("quantity")))
            minimum = _num(item.get("minimum_stock"))
            suggested = max(minimum * 2 - available, 1.0)
            with st.container(border=True):
                columns = st.columns([3, 1, 1, 1])
                columns[0].markdown(f"**{item.get('name', 'Material')}**")
                columns[0].caption(f"Disponible: {available:,.2f} · mínimo: {minimum:,.2f}")
                columns[1].metric("Sugerido", f"{suggested:,.2f}")
                already_open = any(
                    str(request.get("material_name", "")).strip().casefold() == str(item.get("name", "")).strip().casefold()
                    and str(request.get("status", "Pendiente")) in {"Pendiente", "Aprobada"}
                    for request in requests
                )
                if columns[2].button("Crear solicitud", key=f"replenish_{item_id}", use_container_width=True, disabled=already_open):
                    requests.append({
                        "request_id": f"REQ-{uuid4().hex[:8].upper()}",
                        "material_name": str(item.get("name", "Material")),
                        "quantity": suggested,
                        "unit_name": str(item.get("unit_name", "unidad")),
                        "priority": "Alta",
                        "needed_date": (date.today() + timedelta(days=7)).isoformat(),
                        "requested_by": "Inventario",
                        "budget": 0.0,
                        "reason": "Reposición sugerida por existencia mínima.",
                        "status": "Pendiente",
                        "created_at_utc": _now(),
                    })
                    _save("purchase_requests", requests)
                    st.rerun()
                columns[3].metric("Solicitud", "Ya existe" if already_open else "Pendiente")

    render_info_card(
        "Compra protegida",
        "Presupuesto, conciliación y reposiciones quedan incluidos en el respaldo general.",
        "CONTROL DE COMPRAS",
    )
