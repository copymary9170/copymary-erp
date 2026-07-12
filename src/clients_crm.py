"""Gestión avanzada de clientes para CopyMary ERP."""

from datetime import date, datetime
from uuid import uuid4
import csv
import io

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _record_datetime(record: dict) -> datetime | None:
    raw = str(record.get("created_at_utc", record.get("created_at", record.get("date", ""))))
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.fromisoformat(raw[:10])
        except ValueError:
            return None


def _sale_paid(sale: dict, payments: list[dict]) -> float:
    sale_id = str(sale.get("sale_id", ""))
    total = _number(sale.get("total"))
    explicit = sum(
        _number(item.get("amount"))
        for item in payments
        if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
    )
    if explicit > 0:
        return min(explicit, total)
    return total if sale.get("payment_status") == "Pagado" else 0.0


def _client_stats(client_id: str, sales: list[dict], payments: list[dict]) -> dict:
    cancelled = {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    client_sales = [
        sale for sale in sales
        if str(sale.get("client_id", "")) == client_id
        and sale.get("order_status") not in cancelled
    ]
    billed = sum(_number(item.get("total")) for item in client_sales)
    paid = sum(_sale_paid(item, payments) for item in client_sales)
    balance = max(billed - paid, 0.0)
    dates = [value for value in (_record_datetime(item) for item in client_sales) if value]
    last_purchase = max(dates) if dates else None
    days_inactive = (date.today() - last_purchase.date()).days if last_purchase else None
    ticket = billed / len(client_sales) if client_sales else 0.0
    return {
        "sales": client_sales,
        "orders": len(client_sales),
        "billed": billed,
        "paid": paid,
        "balance": balance,
        "last_purchase": last_purchase,
        "days_inactive": days_inactive,
        "ticket": ticket,
    }


def _segment(stats: dict) -> str:
    if stats["balance"] > 0:
        return "Con saldo"
    if stats["orders"] == 0:
        return "Sin compras"
    if stats["days_inactive"] is not None and stats["days_inactive"] >= 60:
        return "Inactivo"
    if stats["billed"] >= 100:
        return "Cliente valioso"
    return "Activo"


def _duplicate_client(clients: list[dict], name: str, phone: str, email: str, ignore_id: str = "") -> str | None:
    normalized_name = name.strip().casefold()
    normalized_phone = "".join(character for character in phone if character.isdigit())
    normalized_email = email.strip().casefold()
    for client in clients:
        if str(client.get("client_id", "")) == ignore_id:
            continue
        existing_name = str(client.get("name", "")).strip().casefold()
        existing_phone = "".join(character for character in str(client.get("phone", "")) if character.isdigit())
        existing_email = str(client.get("email", "")).strip().casefold()
        if normalized_phone and existing_phone == normalized_phone:
            return "Ya existe un cliente con ese teléfono."
        if normalized_email and existing_email == normalized_email:
            return "Ya existe un cliente con ese correo."
        if normalized_name and existing_name == normalized_name:
            return "Ya existe un cliente con ese nombre."
    return None


def _export_clients(clients: list[dict], sales: list[dict], payments: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ID",
        "Nombre",
        "Teléfono",
        "Correo",
        "Tipo",
        "Origen",
        "Pedidos",
        "Facturado",
        "Pagado",
        "Saldo",
        "Última compra",
        "Segmento",
    ])
    for client in clients:
        client_id = str(client.get("client_id", ""))
        stats = _client_stats(client_id, sales, payments)
        writer.writerow([
            client_id,
            client.get("name", ""),
            client.get("phone", ""),
            client.get("email", ""),
            client.get("client_type", "Persona"),
            client.get("source", "No indicado"),
            stats["orders"],
            stats["billed"],
            stats["paid"],
            stats["balance"],
            stats["last_purchase"].date().isoformat() if stats["last_purchase"] else "",
            _segment(stats),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_clients_crm() -> None:
    render_page_header(
        "Clientes",
        "Registra, segmenta y da seguimiento al historial, saldos y actividad de cada cliente.",
    )

    clients = _rows("customers_registry")
    sales = _rows("sales_registry")
    payments = _rows("payment_records")

    client_data = []
    for client in clients:
        client_id = str(client.get("client_id", ""))
        stats = _client_stats(client_id, sales, payments)
        client_data.append((client, stats, _segment(stats)))

    total_billed = sum(item[1]["billed"] for item in client_data)
    total_balance = sum(item[1]["balance"] for item in client_data)
    active_count = sum(1 for _, _, segment in client_data if segment in {"Activo", "Cliente valioso", "Con saldo"})
    inactive_count = sum(1 for _, _, segment in client_data if segment == "Inactivo")

    metrics = st.columns(5)
    metrics[0].metric("Clientes registrados", str(len(clients)))
    metrics[1].metric("Clientes activos", str(active_count))
    metrics[2].metric("Clientes inactivos", str(inactive_count))
    metrics[3].metric("Facturación acumulada", format_money(total_billed))
    metrics[4].metric("Saldo pendiente", format_money(total_balance))

    with st.expander("Registrar nuevo cliente", expanded=not bool(clients)):
        with st.form("customer_crm_form", clear_on_submit=True):
            first = st.columns(2)
            name = first[0].text_input("Nombre o razón social", max_chars=120)
            client_type = first[1].selectbox("Tipo de cliente", ("Persona", "Empresa", "Institución", "Gobierno", "Otro"))
            second = st.columns(2)
            phone = second[0].text_input("Teléfono", max_chars=40)
            email = second[1].text_input("Correo", max_chars=120)
            third = st.columns(2)
            address = third[0].text_input("Dirección", max_chars=180)
            source = third[1].selectbox("Cómo llegó", ("Vecino", "WhatsApp", "Instagram", "Recomendación", "Cliente recurrente", "Otro"))
            notes = st.text_area("Notas", max_chars=500)
            submitted = st.form_submit_button("Registrar cliente", type="primary", use_container_width=True)
        if submitted:
            cleaned_name = name.strip()
            duplicate = _duplicate_client(clients, cleaned_name, phone, email)
            if not cleaned_name:
                st.error("El nombre del cliente es obligatorio.")
            elif duplicate:
                st.error(duplicate)
            else:
                clients.append({
                    "client_id": uuid4().hex[:10],
                    "name": cleaned_name,
                    "client_type": client_type,
                    "phone": phone.strip(),
                    "email": email.strip(),
                    "address": address.strip(),
                    "source": source,
                    "notes": notes.strip(),
                    "created_at_utc": _now(),
                    "updated_at_utc": _now(),
                })
                _save("customers_registry", clients)
                st.success("Cliente registrado.")
                st.rerun()

    st.markdown("### Buscar y segmentar")
    filters = st.columns(3)
    search = filters[0].text_input("Buscar", placeholder="Nombre, teléfono, correo o ID")
    segment_filter = filters[1].selectbox(
        "Segmento",
        ("Todos", "Activo", "Cliente valioso", "Con saldo", "Inactivo", "Sin compras"),
    )
    type_filter = filters[2].selectbox(
        "Tipo",
        ("Todos", "Persona", "Empresa", "Institución", "Gobierno", "Otro"),
    )

    filtered = []
    query = search.strip().casefold()
    for client, stats, segment in client_data:
        searchable = " ".join(
            str(client.get(field, ""))
            for field in ("client_id", "name", "phone", "email", "address", "notes")
        ).casefold()
        if query and query not in searchable:
            continue
        if segment_filter != "Todos" and segment != segment_filter:
            continue
        if type_filter != "Todos" and str(client.get("client_type", "Persona")) != type_filter:
            continue
        filtered.append((client, stats, segment))

    st.caption(f"Mostrando {len(filtered)} de {len(clients)} cliente(s).")

    if clients:
        st.download_button(
            "Descargar clientes CSV",
            data=_export_clients(clients, sales, payments),
            file_name=f"clientes_copymary_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if not filtered:
        st.info("No hay clientes que coincidan con los filtros seleccionados.")

    for client, stats, segment in sorted(filtered, key=lambda item: item[1]["billed"], reverse=True):
        client_id = str(client.get("client_id", ""))
        with st.container(border=True):
            header = st.columns([3, 1])
            with header[0]:
                st.markdown(f"### {client.get('name', 'Cliente')}")
                st.caption(
                    f"ID {client_id} · {client.get('client_type', 'Persona')} · "
                    f"{client.get('phone') or 'Sin teléfono'} · {client.get('email') or 'Sin correo'}"
                )
            header[1].metric("Segmento", segment)

            card_metrics = st.columns(5)
            card_metrics[0].metric("Pedidos", str(stats["orders"]))
            card_metrics[1].metric("Facturado", format_money(stats["billed"]))
            card_metrics[2].metric("Pagado", format_money(stats["paid"]))
            card_metrics[3].metric("Saldo", format_money(stats["balance"]))
            card_metrics[4].metric("Ticket promedio", format_money(stats["ticket"]))

            last_purchase = stats["last_purchase"].date().isoformat() if stats["last_purchase"] else "Sin compras"
            st.caption(
                f"Última compra: {last_purchase} · Origen: {client.get('source', 'No indicado')} · "
                f"Dirección: {client.get('address') or 'No registrada'}"
            )
            if client.get("notes"):
                st.write(str(client["notes"]))

            with st.expander("Editar ficha del cliente"):
                with st.form(f"edit_client_{client_id}"):
                    edit_first = st.columns(2)
                    edited_name = edit_first[0].text_input("Nombre", value=str(client.get("name", "")), key=f"name_{client_id}")
                    edited_type = edit_first[1].selectbox(
                        "Tipo",
                        ("Persona", "Empresa", "Institución", "Gobierno", "Otro"),
                        index=("Persona", "Empresa", "Institución", "Gobierno", "Otro").index(str(client.get("client_type", "Persona"))) if str(client.get("client_type", "Persona")) in ("Persona", "Empresa", "Institución", "Gobierno", "Otro") else 0,
                        key=f"type_{client_id}",
                    )
                    edit_second = st.columns(2)
                    edited_phone = edit_second[0].text_input("Teléfono", value=str(client.get("phone", "")), key=f"phone_{client_id}")
                    edited_email = edit_second[1].text_input("Correo", value=str(client.get("email", "")), key=f"email_{client_id}")
                    edited_address = st.text_input("Dirección", value=str(client.get("address", "")), key=f"address_{client_id}")
                    edited_notes = st.text_area("Notas", value=str(client.get("notes", "")), key=f"notes_{client_id}")
                    save_changes = st.form_submit_button("Guardar cambios", use_container_width=True)
                if save_changes:
                    duplicate = _duplicate_client(clients, edited_name, edited_phone, edited_email, client_id)
                    if not edited_name.strip():
                        st.error("El nombre no puede quedar vacío.")
                    elif duplicate:
                        st.error(duplicate)
                    else:
                        updated_clients = []
                        for current in clients:
                            updated = dict(current)
                            if str(current.get("client_id", "")) == client_id:
                                updated.update({
                                    "name": edited_name.strip(),
                                    "client_type": edited_type,
                                    "phone": edited_phone.strip(),
                                    "email": edited_email.strip(),
                                    "address": edited_address.strip(),
                                    "notes": edited_notes.strip(),
                                    "updated_at_utc": _now(),
                                })
                            updated_clients.append(updated)
                        _save("customers_registry", updated_clients)
                        st.success("Cliente actualizado.")
                        st.rerun()

            if stats["balance"] > 0:
                st.warning(f"Este cliente tiene {format_money(stats['balance'])} pendiente por pagar.")
            if stats["days_inactive"] is not None and stats["days_inactive"] >= 60:
                st.info(f"Han pasado {stats['days_inactive']} días desde su última compra.")

            if st.button("Eliminar cliente", key=f"delete_crm_{client_id}", use_container_width=True):
                if stats["orders"]:
                    st.error("No puedes eliminar un cliente con ventas registradas.")
                else:
                    _save("customers_registry", [item for item in clients if str(item.get("client_id", "")) != client_id])
                    st.rerun()

    render_info_card(
        "Gestión de clientes",
        "Las fichas, segmentos, saldos e historial se calculan con la información comercial de la sesión actual.",
        "CRM DE CLIENTES",
    )
