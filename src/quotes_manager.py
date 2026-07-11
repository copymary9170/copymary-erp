"""Gestión mejorada de cotizaciones para CopyMary ERP."""

from datetime import date, datetime, timedelta
from uuid import uuid4
import csv
import io

import streamlit as st

from src.commercial_documents import _build_document_html
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save

STATUSES = ("Borrador", "Enviada", "En seguimiento", "Aceptada", "Rechazada", "Vencida", "Convertida")


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _created(quote: dict) -> datetime | None:
    raw = str(quote.get("created_at_utc", ""))
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _expiry(quote: dict) -> date | None:
    created = _created(quote)
    return created.date() + timedelta(days=int(_num(quote.get("validity_days")) or 7)) if created else None


def _status(quote: dict) -> str:
    current = str(quote.get("status", "Borrador"))
    expiry = _expiry(quote)
    if current not in {"Aceptada", "Rechazada", "Convertida"} and expiry and expiry < date.today():
        return "Vencida"
    return current if current in STATUSES else "Borrador"


def _total(quote: dict) -> float:
    subtotal = sum(_num(item.get("quantity")) * _num(item.get("unit_price")) for item in quote.get("items", []) if isinstance(item, dict))
    return max(subtotal - _num(quote.get("discount")), 0.0)


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Sin cliente"


def _export(quotes: list[dict], clients: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Cliente", "Estado", "Vence", "Total", "Versión", "Venta vinculada"])
    for quote in quotes:
        expiry = _expiry(quote)
        writer.writerow([
            quote.get("quote_id", ""),
            _client_name(str(quote.get("client_id", "")), clients),
            _status(quote),
            expiry.isoformat() if expiry else "",
            _total(quote),
            quote.get("version", 1),
            quote.get("converted_sale_id", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_quotes_manager() -> None:
    render_page_header("Cotizaciones", "Crea propuestas, controla su vigencia y conviértelas en ventas con trazabilidad.")
    clients = _rows("customers_registry")
    quotes = _rows("quotes_registry")
    sales = _rows("sales_registry")

    metrics = st.columns(4)
    metrics[0].metric("Cotizaciones", str(len(quotes)))
    metrics[1].metric("Valor cotizado", format_money(sum(_total(item) for item in quotes)))
    metrics[2].metric("Activas", str(sum(1 for item in quotes if _status(item) in {"Borrador", "Enviada", "En seguimiento", "Aceptada"})))
    metrics[3].metric("Convertidas", str(sum(1 for item in quotes if item.get("converted_sale_id"))))

    client_options = {"Sin cliente": ""}
    for client in clients:
        client_options[f"{client.get('name', 'Cliente')} · {client.get('client_id', '')}"] = str(client.get("client_id", ""))

    with st.expander("Crear nueva cotización", expanded=not bool(quotes)):
        with st.form("quotes_manager_form", clear_on_submit=True):
            top = st.columns(3)
            selected_client = top[0].selectbox("Cliente", tuple(client_options.keys()))
            validity = top[1].number_input("Vigencia en días", min_value=1, value=7, step=1)
            initial_status = top[2].selectbox("Estado", ("Borrador", "Enviada"))
            title = st.text_input("Título o referencia", max_chars=140)
            items: list[dict] = []
            for index in range(1, 7):
                columns = st.columns([3, 1, 1])
                description = columns[0].text_input("Descripción", key=f"qm_desc_{index}")
                quantity = columns[1].number_input("Cantidad", min_value=0.0, value=0.0, step=1.0, key=f"qm_qty_{index}")
                unit_price = columns[2].number_input("Precio", min_value=0.0, value=0.0, step=0.5, key=f"qm_price_{index}")
                if description.strip() and quantity > 0 and unit_price > 0:
                    items.append({"description": description.strip(), "quantity": float(quantity), "unit_price": float(unit_price)})
            bottom = st.columns(3)
            discount = bottom[0].number_input("Descuento", min_value=0.0, value=0.0, step=0.5)
            cost = bottom[1].number_input("Costo estimado", min_value=0.0, value=0.0, step=0.5)
            deposit = bottom[2].number_input("Anticipo requerido", min_value=0.0, value=0.0, step=0.5)
            terms = st.text_area("Condiciones comerciales", max_chars=700)
            submitted = st.form_submit_button("Guardar cotización", type="primary", use_container_width=True)
        if submitted:
            quote = {"items": items, "discount": float(discount)}
            total = _total(quote)
            if not items:
                st.error("Agrega al menos un concepto completo.")
            elif total <= 0:
                st.error("El total debe ser mayor que cero.")
            elif deposit > total:
                st.error("El anticipo no puede superar el total.")
            else:
                quotes.append({
                    "quote_id": uuid4().hex[:10], "created_at_utc": _now(), "updated_at_utc": _now(),
                    "client_id": client_options[selected_client], "title": title.strip(), "validity_days": int(validity),
                    "items": items, "discount": float(discount), "estimated_cost": float(cost),
                    "deposit_required": float(deposit), "terms": terms.strip(), "status": initial_status,
                    "converted_sale_id": "", "version": 1,
                })
                _save("quotes_registry", quotes)
                st.rerun()

    filters = st.columns(3)
    search = filters[0].text_input("Buscar", placeholder="ID, cliente, título o concepto")
    state_filter = filters[1].selectbox("Estado", ("Todos", *STATUSES))
    validity_filter = filters[2].selectbox("Vigencia", ("Todas", "Vigentes", "Vencidas", "Vencen en 7 días"))
    query = search.strip().casefold()
    filtered = []
    for quote in quotes:
        status = _status(quote)
        expiry = _expiry(quote)
        text = " ".join([str(quote.get("quote_id", "")), str(quote.get("title", "")), _client_name(str(quote.get("client_id", "")), clients), " ".join(str(item.get("description", "")) for item in quote.get("items", []) if isinstance(item, dict))]).casefold()
        if query and query not in text:
            continue
        if state_filter != "Todos" and status != state_filter:
            continue
        if validity_filter == "Vigentes" and (not expiry or expiry < date.today()):
            continue
        if validity_filter == "Vencidas" and status != "Vencida":
            continue
        if validity_filter == "Vencen en 7 días" and (not expiry or not 0 <= (expiry - date.today()).days <= 7):
            continue
        filtered.append(quote)

    if quotes:
        st.download_button("Descargar resumen CSV", _export(quotes, clients), f"cotizaciones_{date.today().isoformat()}.csv", "text/csv", use_container_width=True)

    for quote in reversed(filtered):
        quote_id = str(quote.get("quote_id", ""))
        items = [dict(item) for item in quote.get("items", []) if isinstance(item, dict)]
        total = _total(quote)
        expiry = _expiry(quote)
        status = _status(quote)
        margin = (total - _num(quote.get("estimated_cost"))) / total * 100 if total else 0.0
        client_name = _client_name(str(quote.get("client_id", "")), clients)
        with st.container(border=True):
            header = st.columns([3, 1])
            header[0].markdown(f"### {quote.get('title') or f'Cotización {quote_id}'}")
            header[0].caption(f"ID {quote_id} · {client_name} · Versión {quote.get('version', 1)}")
            header[1].metric("Estado", status)
            cards = st.columns(5)
            cards[0].metric("Total", format_money(total))
            cards[1].metric("Conceptos", str(len(items)))
            cards[2].metric("Vence", expiry.isoformat() if expiry else "Sin fecha")
            cards[3].metric("Anticipo", format_money(_num(quote.get("deposit_required"))))
            cards[4].metric("Margen", f"{margin:,.1f}%")
            if status == "Vencida":
                st.error("Esta cotización está vencida.")
            elif expiry and 0 <= (expiry - date.today()).days <= 7:
                st.warning(f"Vence en {(expiry - date.today()).days} día(s).")
            for item in items:
                st.write(f"{item.get('description', '')}: {_num(item.get('quantity')):,.2f} × {format_money(_num(item.get('unit_price')))}")
            actions = st.columns(4)
            actions[0].download_button("Descargar HTML", _build_document_html("Cotización", quote_id, client_name, str(quote.get("created_at_utc", "")), items, _num(quote.get("discount")), str(quote.get("terms", ""))), f"cotizacion_{quote_id}.html", "text/html", use_container_width=True, key=f"qm_download_{quote_id}")
            new_status = actions[1].selectbox("Estado", STATUSES, index=STATUSES.index(status), key=f"qm_status_{quote_id}")
            if actions[2].button("Guardar", key=f"qm_save_{quote_id}", use_container_width=True):
                for stored in quotes:
                    if str(stored.get("quote_id", "")) == quote_id:
                        stored["status"] = new_status
                        stored["updated_at_utc"] = _now()
                _save("quotes_registry", quotes)
                st.rerun()
            if actions[3].button("Convertir en venta", key=f"qm_convert_{quote_id}", use_container_width=True, type="primary", disabled=bool(quote.get("converted_sale_id"))):
                sale_id = uuid4().hex[:10]
                sales.append({"sale_id": sale_id, "created_at_utc": _now(), "client_id": str(quote.get("client_id", "")), "description": " + ".join(str(item.get("description", "")) for item in items)[:140], "quantity": 1.0, "unit_price": total, "discount": 0.0, "total": total, "estimated_cost": _num(quote.get("estimated_cost")), "payment_status": "Pendiente", "order_status": "Pendiente", "payment_method": "Otro", "notes": f"Creada desde cotización {quote_id}", "cash_registered": False, "source_quote_id": quote_id, "quote_items": items})
                for stored in quotes:
                    if str(stored.get("quote_id", "")) == quote_id:
                        stored["status"] = "Convertida"
                        stored["converted_sale_id"] = sale_id
                _save("sales_registry", sales)
                _save("quotes_registry", quotes)
                st.rerun()
            secondary = st.columns(2)
            if secondary[0].button("Duplicar como nueva versión", key=f"qm_duplicate_{quote_id}", use_container_width=True):
                duplicate = dict(quote)
                duplicate.update({"quote_id": uuid4().hex[:10], "created_at_utc": _now(), "updated_at_utc": _now(), "status": "Borrador", "converted_sale_id": "", "version": int(_num(quote.get("version")) or 1) + 1, "parent_quote_id": quote_id, "items": [dict(item) for item in items]})
                quotes.append(duplicate)
                _save("quotes_registry", quotes)
                st.rerun()
            if secondary[1].button("Eliminar", key=f"qm_delete_{quote_id}", use_container_width=True, disabled=bool(quote.get("converted_sale_id"))):
                _save("quotes_registry", [item for item in quotes if str(item.get("quote_id", "")) != quote_id])
                st.rerun()

    render_info_card("Trazabilidad", "Estados, vigencia, versiones y ventas vinculadas permanecen en el respaldo general.", "GESTIÓN DE COTIZACIONES")
