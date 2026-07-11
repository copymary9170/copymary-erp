"""Gestión profesional de comprobantes de pago para CopyMary ERP."""

from datetime import date
from html import escape
from uuid import uuid4
import csv
import io

import streamlit as st

from src import session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    section = "receipts_registry"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Comprobantes"
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


def _client(client_id: str, clients: list[dict]) -> dict:
    for item in clients:
        if str(item.get("client_id", "")) == client_id:
            return dict(item)
    return {}


def _business_settings() -> dict:
    raw = st.session_state.get("general_settings", {})
    return dict(raw) if isinstance(raw, dict) else {}


def _payment_label(payment: dict, sales: list[dict], clients: list[dict]) -> str:
    sale_id = str(payment.get("sale_id", ""))
    sale = next((item for item in sales if str(item.get("sale_id", "")) == sale_id), {})
    customer = _client(str(sale.get("client_id", "")), clients)
    return (
        f"{customer.get('name', 'Sin cliente')} · Venta {sale_id} · "
        f"{format_money(_num(payment.get('amount')))} · {payment.get('payment_method', payment.get('method', 'Otro'))}"
    )


def _receipt_html(receipt: dict, sale: dict, client: dict) -> bytes:
    currency = get_currency()
    settings = _business_settings()
    business_name = str(settings.get("business_name", "Copy Mary"))
    business_phone = str(settings.get("phone", settings.get("business_phone", "")))
    business_address = str(settings.get("address", settings.get("business_address", "")))
    amount = _num(receipt.get("amount"))
    sale_total = _num(sale.get("total"))
    previous_paid = _num(receipt.get("previous_paid"))
    remaining = max(sale_total - previous_paid - amount, 0.0)
    status = str(receipt.get("status", "Emitido"))
    watermark = '<div class="void">ANULADO</div>' if status == "Anulado" else ""
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Comprobante {escape(str(receipt.get('receipt_id', '')))}</title>
<style>
body{{font-family:Arial,sans-serif;margin:0;background:#f3f4f6;color:#1f2937}}.sheet{{max-width:760px;margin:28px auto;background:white;padding:34px;border-radius:18px;box-shadow:0 10px 30px rgba(0,0,0,.08);position:relative}}h1{{margin:0;color:#6d4aff}}h2{{margin:8px 0 24px}}.meta,.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.box{{padding:14px;border:1px solid #e5e7eb;border-radius:12px}}.amount{{font-size:28px;font-weight:800;color:#0f766e}}.totals{{margin-top:20px;padding:16px;background:#f8fafc;border-radius:12px}}.footer{{margin-top:28px;color:#64748b;font-size:13px}}.void{{position:absolute;inset:42% 12%;transform:rotate(-18deg);font-size:72px;font-weight:900;color:rgba(220,38,38,.18);text-align:center;border:8px solid rgba(220,38,38,.18)}}@media print{{body{{background:white}}.sheet{{box-shadow:none;margin:0;max-width:none}}}}
</style></head><body><div class="sheet">{watermark}
<h1>{escape(business_name)}</h1><div>{escape(business_address)} {escape(business_phone)}</div>
<h2>Comprobante de pago</h2>
<div class="meta"><div class="box"><strong>Número</strong><br>{escape(str(receipt.get('receipt_id', '')))}</div><div class="box"><strong>Fecha</strong><br>{escape(str(receipt.get('issued_at_utc', '')))}</div></div>
<div class="grid" style="margin-top:12px"><div class="box"><strong>Cliente</strong><br>{escape(str(client.get('name', 'Cliente no registrado')))}<br>{escape(str(client.get('phone', '')))}</div><div class="box"><strong>Venta vinculada</strong><br>{escape(str(sale.get('sale_id', '')))}<br>{escape(str(sale.get('description', 'Venta')))}</div></div>
<div class="box" style="margin-top:12px"><strong>Monto recibido</strong><div class="amount">{escape(format_money(amount, currency))}</div><div>Método: {escape(str(receipt.get('payment_method', 'Otro')))} · Referencia: {escape(str(receipt.get('reference', '') or 'Sin referencia'))}</div></div>
<div class="totals">Total de la venta: <strong>{escape(format_money(sale_total, currency))}</strong><br>Pagado antes: <strong>{escape(format_money(previous_paid, currency))}</strong><br>Saldo restante: <strong>{escape(format_money(remaining, currency))}</strong></div>
<div class="box" style="margin-top:12px"><strong>Concepto:</strong> {escape(str(receipt.get('concept', '') or sale.get('description', 'Pago de venta')))}<br><strong>Observaciones:</strong> {escape(str(receipt.get('notes', '') or 'Sin observaciones'))}</div>
<div class="footer">Estado: {escape(status)} · Generado por CopyMary ERP. Este documento acredita el pago registrado en el sistema.</div>
</div></body></html>"""
    return html.encode("utf-8")


def _export(receipts: list[dict], sales: list[dict], clients: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Comprobante", "Fecha", "Cliente", "Venta", "Monto", "Método", "Referencia", "Estado"])
    for receipt in receipts:
        sale = next((item for item in sales if str(item.get("sale_id", "")) == str(receipt.get("sale_id", ""))), {})
        client = _client(str(sale.get("client_id", "")), clients)
        writer.writerow([
            receipt.get("receipt_id", ""), receipt.get("issued_at_utc", ""), client.get("name", ""),
            receipt.get("sale_id", ""), receipt.get("amount", 0), receipt.get("payment_method", ""),
            receipt.get("reference", ""), receipt.get("status", "Emitido"),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_receipts_plus() -> None:
    render_page_header(
        "Comprobantes",
        "Emite, consulta, descarga y anula comprobantes con trazabilidad de cada pago.",
    )
    clients = _rows("customers_registry")
    sales = _rows("sales_registry")
    payments = [item for item in _rows("payment_records") if not item.get("reversed")]
    receipts = _rows("receipts_registry")

    issued = sum(1 for item in receipts if item.get("status", "Emitido") == "Emitido")
    voided = sum(1 for item in receipts if item.get("status") == "Anulado")
    total_issued = sum(_num(item.get("amount")) for item in receipts if item.get("status", "Emitido") == "Emitido")
    pending_payments = [item for item in payments if not any(str(r.get("payment_id", "")) == str(item.get("payment_id", "")) and r.get("status") != "Anulado" for r in receipts)]

    metrics = st.columns(4)
    metrics[0].metric("Emitidos", str(issued))
    metrics[1].metric("Anulados", str(voided))
    metrics[2].metric("Monto comprobado", format_money(total_issued))
    metrics[3].metric("Pagos sin comprobante", str(len(pending_payments)))

    with st.expander("Emitir nuevo comprobante", expanded=bool(pending_payments)):
        if not pending_payments:
            st.info("Todos los pagos registrados ya tienen comprobante activo.")
        else:
            options = {_payment_label(item, sales, clients): item for item in pending_payments}
            with st.form("receipt_issue_form", clear_on_submit=True):
                selected = st.selectbox("Pago registrado", tuple(options.keys()))
                payment = options[selected]
                sale = next((item for item in sales if str(item.get("sale_id", "")) == str(payment.get("sale_id", ""))), {})
                previous_paid = sum(_num(item.get("amount")) for item in payments if str(item.get("sale_id", "")) == str(sale.get("sale_id", "")) and str(item.get("payment_id", "")) != str(payment.get("payment_id", "")))
                columns = st.columns(2)
                reference = columns[0].text_input("Referencia", value=str(payment.get("reference", "")))
                concept = columns[1].text_input("Concepto", value=str(sale.get("description", "Pago de venta")))
                notes = st.text_area("Observaciones", max_chars=500)
                submitted = st.form_submit_button("Emitir comprobante", type="primary", use_container_width=True)
            if submitted:
                receipts.append({
                    "receipt_id": f"REC-{date.today().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
                    "payment_id": str(payment.get("payment_id", "")),
                    "sale_id": str(payment.get("sale_id", "")),
                    "issued_at_utc": _now(),
                    "amount": _num(payment.get("amount")),
                    "payment_method": str(payment.get("payment_method", payment.get("method", "Otro"))),
                    "reference": reference.strip(),
                    "concept": concept.strip(),
                    "notes": notes.strip(),
                    "previous_paid": previous_paid,
                    "status": "Emitido",
                })
                _save("receipts_registry", receipts)
                st.rerun()

    st.markdown("### Consultar comprobantes")
    filters = st.columns(3)
    search = filters[0].text_input("Buscar", placeholder="Número, cliente, venta o referencia")
    status_filter = filters[1].selectbox("Estado", ("Todos", "Emitido", "Anulado"))
    method_filter = filters[2].selectbox("Método", ("Todos", *sorted({str(item.get('payment_method', 'Otro')) for item in receipts})))

    query = search.strip().casefold()
    filtered = []
    for receipt in receipts:
        sale = next((item for item in sales if str(item.get("sale_id", "")) == str(receipt.get("sale_id", ""))), {})
        client = _client(str(sale.get("client_id", "")), clients)
        text = " ".join((str(receipt.get("receipt_id", "")), str(receipt.get("sale_id", "")), str(receipt.get("reference", "")), str(client.get("name", "")))).casefold()
        if query and query not in text:
            continue
        if status_filter != "Todos" and receipt.get("status", "Emitido") != status_filter:
            continue
        if method_filter != "Todos" and str(receipt.get("payment_method", "Otro")) != method_filter:
            continue
        filtered.append(receipt)

    if receipts:
        st.download_button("Exportar comprobantes CSV", _export(receipts, sales, clients), f"comprobantes_{date.today().isoformat()}.csv", "text/csv", use_container_width=True)

    for receipt in reversed(filtered):
        sale = next((item for item in sales if str(item.get("sale_id", "")) == str(receipt.get("sale_id", ""))), {})
        client = _client(str(sale.get("client_id", "")), clients)
        receipt_id = str(receipt.get("receipt_id", ""))
        with st.container(border=True):
            header = st.columns([3, 1])
            header[0].markdown(f"### {receipt_id}")
            header[0].caption(f"{client.get('name', 'Sin cliente')} · Venta {receipt.get('sale_id', '')} · {receipt.get('issued_at_utc', '')}")
            header[1].metric("Estado", str(receipt.get("status", "Emitido")))
            cards = st.columns(3)
            cards[0].metric("Monto", format_money(_num(receipt.get("amount"))))
            cards[1].metric("Método", str(receipt.get("payment_method", "Otro")))
            cards[2].metric("Referencia", str(receipt.get("reference") or "Sin referencia"))
            actions = st.columns(2)
            actions[0].download_button("Descargar HTML", _receipt_html(receipt, sale, client), f"comprobante_{receipt_id}.html", "text/html", use_container_width=True, key=f"receipt_download_{receipt_id}")
            if actions[1].button("Anular comprobante", key=f"receipt_void_{receipt_id}", use_container_width=True, disabled=receipt.get("status") == "Anulado"):
                updated = []
                for item in receipts:
                    row = dict(item)
                    if str(row.get("receipt_id", "")) == receipt_id:
                        row["status"] = "Anulado"
                        row["voided_at_utc"] = _now()
                    updated.append(row)
                _save("receipts_registry", updated)
                st.rerun()

    render_info_card(
        "Trazabilidad documental",
        "Cada comprobante conserva su pago, venta, referencia, estado y archivo descargable dentro del respaldo general.",
        "COMPROBANTES",
    )
