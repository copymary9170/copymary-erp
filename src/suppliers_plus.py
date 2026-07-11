"""Gestión ampliada de proveedores para CopyMary ERP."""

from datetime import date, datetime
import csv
import io

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


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


def _supplier_purchases(supplier_id: str, purchases: list[dict]) -> list[dict]:
    return [item for item in purchases if str(item.get("supplier_id", "")) == supplier_id]


def _duplicate(suppliers: list[dict], name: str, phone: str, email: str, ignore_id: str = "") -> str | None:
    name_key = name.strip().casefold()
    phone_key = "".join(character for character in phone if character.isdigit())
    email_key = email.strip().casefold()
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")) == ignore_id:
            continue
        if name_key and str(supplier.get("name", "")).strip().casefold() == name_key:
            return "Ya existe un proveedor con ese nombre."
        existing_phone = "".join(character for character in str(supplier.get("phone", "")) if character.isdigit())
        if phone_key and existing_phone == phone_key:
            return "Ya existe un proveedor con ese teléfono."
        if email_key and str(supplier.get("email", "")).strip().casefold() == email_key:
            return "Ya existe un proveedor con ese correo."
    return None


def _export(suppliers: list[dict], purchases: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ID", "Proveedor", "Teléfono", "Correo", "Categorías", "Condiciones de pago",
        "Tiempo de entrega", "Calificación", "Estado", "Compras", "Total comprado", "Última compra",
    ])
    for supplier in suppliers:
        supplier_id = str(supplier.get("supplier_id", ""))
        supplier_purchases = _supplier_purchases(supplier_id, purchases)
        dates = [value for value in (_as_datetime(item.get("created_at_utc")) for item in supplier_purchases) if value]
        writer.writerow([
            supplier_id,
            supplier.get("name", ""),
            supplier.get("phone", ""),
            supplier.get("email", ""),
            supplier.get("products", ""),
            supplier.get("payment_terms", ""),
            supplier.get("lead_time_days", 0),
            supplier.get("rating", 0),
            supplier.get("status", "Activo"),
            len(supplier_purchases),
            sum(_num(item.get("total")) for item in supplier_purchases),
            max(dates).date().isoformat() if dates else "",
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_suppliers_plus() -> None:
    render_page_header(
        "Proveedores",
        "Registra, evalúa y compara proveedores por precio, servicio, tiempos y condiciones comerciales.",
    )

    suppliers = _rows("suppliers_registry")
    purchases = _rows("purchases_registry")

    total_purchased = sum(_num(item.get("total")) for item in purchases)
    active = sum(1 for item in suppliers if str(item.get("status", "Activo")) == "Activo")
    inactive = sum(1 for item in suppliers if str(item.get("status", "Activo")) == "Inactivo")
    rated = [item for item in suppliers if _num(item.get("rating")) > 0]
    average_rating = sum(_num(item.get("rating")) for item in rated) / len(rated) if rated else 0.0

    metrics = st.columns(4)
    metrics[0].metric("Proveedores", str(len(suppliers)))
    metrics[1].metric("Activos", str(active))
    metrics[2].metric("Total comprado", format_money(total_purchased))
    metrics[3].metric("Calificación promedio", f"{average_rating:,.1f}/5")

    with st.expander("Registrar proveedor", expanded=not bool(suppliers)):
        with st.form("supplier_plus_form", clear_on_submit=True):
            first = st.columns(3)
            name = first[0].text_input("Nombre o razón social", max_chars=120)
            supplier_type = first[1].selectbox("Tipo", ("Mayorista", "Distribuidor", "Fabricante", "Servicio", "Otro"))
            status = first[2].selectbox("Estado", ("Activo", "Inactivo", "En evaluación"))
            second = st.columns(3)
            phone = second[0].text_input("Teléfono", max_chars=40)
            email = second[1].text_input("Correo", max_chars=120)
            contact_person = second[2].text_input("Persona de contacto", max_chars=120)
            third = st.columns(3)
            products = third[0].text_input("Productos o categorías", max_chars=180)
            payment_terms = third[1].selectbox("Condiciones de pago", ("Contado", "7 días", "15 días", "30 días", "Crédito especial", "Otro"))
            lead_time_days = third[2].number_input("Tiempo de entrega estimado", min_value=0, value=0, step=1)
            address = st.text_input("Dirección", max_chars=180)
            notes = st.text_area("Notas", max_chars=500)
            submitted = st.form_submit_button("Registrar proveedor", type="primary", use_container_width=True)
        if submitted:
            duplicate = _duplicate(suppliers, name, phone, email)
            if not name.strip():
                st.error("El nombre del proveedor es obligatorio.")
            elif duplicate:
                st.error(duplicate)
            else:
                suppliers.append({
                    "supplier_id": f"SUP-{len(suppliers) + 1:04d}",
                    "name": name.strip(),
                    "supplier_type": supplier_type,
                    "status": status,
                    "phone": phone.strip(),
                    "email": email.strip(),
                    "contact_person": contact_person.strip(),
                    "products": products.strip(),
                    "payment_terms": payment_terms,
                    "lead_time_days": int(lead_time_days),
                    "address": address.strip(),
                    "notes": notes.strip(),
                    "rating": 0.0,
                    "created_at_utc": _now(),
                    "updated_at_utc": _now(),
                })
                _save("suppliers_registry", suppliers)
                st.rerun()

    st.markdown("### Buscar y filtrar")
    filters = st.columns(4)
    search = filters[0].text_input("Buscar", placeholder="Nombre, teléfono, correo o categoría")
    status_filter = filters[1].selectbox("Estado", ("Todos", "Activo", "Inactivo", "En evaluación"))
    type_filter = filters[2].selectbox("Tipo", ("Todos", "Mayorista", "Distribuidor", "Fabricante", "Servicio", "Otro"))
    activity_filter = filters[3].selectbox("Actividad", ("Todos", "Con compras", "Sin compras", "Sin compras en 90 días"))

    query = search.strip().casefold()
    filtered = []
    for supplier in suppliers:
        supplier_id = str(supplier.get("supplier_id", ""))
        supplier_purchases = _supplier_purchases(supplier_id, purchases)
        dates = [value for value in (_as_datetime(item.get("created_at_utc")) for item in supplier_purchases) if value]
        last_purchase = max(dates) if dates else None
        searchable = " ".join(str(supplier.get(field, "")) for field in ("name", "phone", "email", "products", "contact_person", "supplier_id")).casefold()
        if query and query not in searchable:
            continue
        if status_filter != "Todos" and str(supplier.get("status", "Activo")) != status_filter:
            continue
        if type_filter != "Todos" and str(supplier.get("supplier_type", "Otro")) != type_filter:
            continue
        if activity_filter == "Con compras" and not supplier_purchases:
            continue
        if activity_filter == "Sin compras" and supplier_purchases:
            continue
        if activity_filter == "Sin compras en 90 días" and last_purchase and (date.today() - last_purchase.date()).days < 90:
            continue
        filtered.append((supplier, supplier_purchases, last_purchase))

    st.caption(f"Mostrando {len(filtered)} de {len(suppliers)} proveedor(es).")
    if suppliers:
        st.download_button(
            "Descargar proveedores CSV",
            data=_export(suppliers, purchases),
            file_name=f"proveedores_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    for supplier, supplier_purchases, last_purchase in sorted(filtered, key=lambda item: sum(_num(row.get("total")) for row in item[1]), reverse=True):
        supplier_id = str(supplier.get("supplier_id", ""))
        total = sum(_num(item.get("total")) for item in supplier_purchases)
        pending = sum(1 for item in supplier_purchases if str(item.get("payment_status", "")) != "Pagado")
        average_order = total / len(supplier_purchases) if supplier_purchases else 0.0
        with st.container(border=True):
            header = st.columns([3, 1])
            header[0].markdown(f"### {supplier.get('name', 'Proveedor')}")
            header[0].caption(
                f"{supplier_id} · {supplier.get('supplier_type', 'Otro')} · "
                f"{supplier.get('contact_person') or 'Sin contacto'} · {supplier.get('phone') or 'Sin teléfono'}"
            )
            header[1].metric("Estado", str(supplier.get("status", "Activo")))

            cards = st.columns(5)
            cards[0].metric("Compras", str(len(supplier_purchases)))
            cards[1].metric("Total comprado", format_money(total))
            cards[2].metric("Ticket promedio", format_money(average_order))
            cards[3].metric("Pendientes", str(pending))
            cards[4].metric("Calificación", f"{_num(supplier.get('rating')):,.1f}/5")

            st.caption(
                f"Última compra: {last_purchase.date().isoformat() if last_purchase else 'Sin compras'} · "
                f"Pago: {supplier.get('payment_terms', 'No definido')} · "
                f"Entrega estimada: {supplier.get('lead_time_days', 0)} día(s)"
            )
            if supplier.get("products"):
                st.write(f"**Productos o categorías:** {supplier.get('products')}")
            if supplier.get("notes"):
                st.write(str(supplier.get("notes")))

            with st.expander("Editar y evaluar proveedor"):
                with st.form(f"edit_supplier_{supplier_id}"):
                    first = st.columns(3)
                    edited_name = first[0].text_input("Nombre", value=str(supplier.get("name", "")), key=f"sup_name_{supplier_id}")
                    edited_status = first[1].selectbox("Estado", ("Activo", "Inactivo", "En evaluación"), index=("Activo", "Inactivo", "En evaluación").index(str(supplier.get("status", "Activo"))) if str(supplier.get("status", "Activo")) in ("Activo", "Inactivo", "En evaluación") else 0, key=f"sup_status_{supplier_id}")
                    rating = first[2].slider("Calificación", min_value=0.0, max_value=5.0, value=float(_num(supplier.get("rating"))), step=0.5, key=f"sup_rating_{supplier_id}")
                    second = st.columns(3)
                    edited_phone = second[0].text_input("Teléfono", value=str(supplier.get("phone", "")), key=f"sup_phone_{supplier_id}")
                    edited_email = second[1].text_input("Correo", value=str(supplier.get("email", "")), key=f"sup_email_{supplier_id}")
                    edited_contact = second[2].text_input("Contacto", value=str(supplier.get("contact_person", "")), key=f"sup_contact_{supplier_id}")
                    third = st.columns(3)
                    edited_products = third[0].text_input("Productos", value=str(supplier.get("products", "")), key=f"sup_products_{supplier_id}")
                    edited_terms = third[1].text_input("Condiciones", value=str(supplier.get("payment_terms", "")), key=f"sup_terms_{supplier_id}")
                    edited_lead = third[2].number_input("Tiempo de entrega", min_value=0, value=int(_num(supplier.get("lead_time_days"))), step=1, key=f"sup_lead_{supplier_id}")
                    edited_notes = st.text_area("Notas", value=str(supplier.get("notes", "")), key=f"sup_notes_{supplier_id}")
                    save_changes = st.form_submit_button("Guardar cambios", type="primary", use_container_width=True)
                if save_changes:
                    duplicate = _duplicate(suppliers, edited_name, edited_phone, edited_email, supplier_id)
                    if not edited_name.strip():
                        st.error("El nombre no puede quedar vacío.")
                    elif duplicate:
                        st.error(duplicate)
                    else:
                        updated = []
                        for current in suppliers:
                            row = dict(current)
                            if str(row.get("supplier_id", "")) == supplier_id:
                                row.update({
                                    "name": edited_name.strip(),
                                    "status": edited_status,
                                    "rating": float(rating),
                                    "phone": edited_phone.strip(),
                                    "email": edited_email.strip(),
                                    "contact_person": edited_contact.strip(),
                                    "products": edited_products.strip(),
                                    "payment_terms": edited_terms.strip(),
                                    "lead_time_days": int(edited_lead),
                                    "notes": edited_notes.strip(),
                                    "updated_at_utc": _now(),
                                })
                            updated.append(row)
                        _save("suppliers_registry", updated)
                        st.rerun()

            if st.button("Eliminar proveedor", key=f"delete_supplier_plus_{supplier_id}", use_container_width=True):
                if supplier_purchases:
                    st.error("No puedes eliminar un proveedor con compras registradas.")
                else:
                    _save("suppliers_registry", [item for item in suppliers if str(item.get("supplier_id", "")) != supplier_id])
                    st.rerun()

    render_info_card(
        "Evaluación de proveedores",
        "La ficha, el historial de compras, las condiciones y la calificación se guardan en la sesión y forman parte del respaldo general.",
        "PROVEEDORES",
    )
