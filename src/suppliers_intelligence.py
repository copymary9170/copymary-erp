"""Evaluación, incidencias, documentos y precios de proveedores."""

from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src import session_backup, suppliers_plus as base
from src.components import render_info_card, render_page_header
from src.money import format_money


def _activate_backup() -> None:
    sections = (
        ("supplier_events", "Incidencias de proveedores"),
        ("supplier_documents", "Documentos de proveedores"),
        ("supplier_price_lists", "Precios de proveedores"),
    )
    for section, label in sections:
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


def _supplier_name(supplier_id: str, suppliers: list[dict]) -> str:
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")) == supplier_id:
            return str(supplier.get("name", "Proveedor"))
    return "Proveedor no disponible"


def _update_supplier(supplier_id: str, updates: dict) -> None:
    suppliers = _rows("suppliers_registry")
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")) == supplier_id:
            supplier.update(updates)
            supplier["updated_at_utc"] = _now()
    _save("suppliers_registry", suppliers)


def _score(supplier: dict, events: list[dict]) -> tuple[float, str]:
    supplier_id = str(supplier.get("supplier_id", ""))
    quality = _num(supplier.get("quality_score"), _num(supplier.get("rating"), 0.0))
    delivery = _num(supplier.get("delivery_score"), 0.0)
    price = _num(supplier.get("price_score"), 0.0)
    service = _num(supplier.get("service_score"), 0.0)
    values = [value for value in (quality, delivery, price, service) if value > 0]
    average = sum(values) / len(values) if values else 0.0
    serious = sum(
        1 for event in events
        if str(event.get("supplier_id", "")) == supplier_id
        and str(event.get("severity", "")) in {"Alta", "Crítica"}
        and str(event.get("status", "Abierta")) != "Cerrada"
    )
    adjusted = max(average - serious * 0.75, 0.0)
    if serious >= 2 or adjusted < 2:
        return adjusted, "Crítico"
    if serious or adjusted < 3:
        return adjusted, "Alto"
    if adjusted < 4:
        return adjusted, "Medio"
    return adjusted, "Bajo"


def render_suppliers_intelligence() -> None:
    render_page_header(
        "Proveedores",
        "Evalúa desempeño, controla incidencias y compara precios antes de comprar.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_suppliers_plus()
    finally:
        base.render_page_header = original_header

    suppliers = _rows("suppliers_registry")
    events = _rows("supplier_events")
    documents = _rows("supplier_documents")
    prices = _rows("supplier_price_lists")
    today = date.today()

    ranked = sorted(
        [(supplier, *_score(supplier, events)) for supplier in suppliers],
        key=lambda item: item[1],
        reverse=True,
    )
    open_events = [item for item in events if str(item.get("status", "Abierta")) != "Cerrada"]
    expired_documents = [
        item for item in documents
        if _as_date(item.get("expiry_date")) and _as_date(item.get("expiry_date")) < today
    ]
    preferred = [item for item in suppliers if item.get("preferred")]

    st.divider()
    metrics = st.columns(4)
    metrics[0].metric("Preferidos", str(len(preferred)))
    metrics[1].metric("Incidencias abiertas", str(len(open_events)))
    metrics[2].metric("Documentos vencidos", str(len(expired_documents)))
    metrics[3].metric("Precios registrados", str(len(prices)))

    if expired_documents:
        st.error(f"Hay {len(expired_documents)} documento(s) de proveedor vencido(s).")
    if any(level == "Crítico" for _, _, level in ranked):
        st.error("Hay proveedores clasificados con riesgo crítico.")

    evaluation_tab, incident_tab, document_tab, price_tab, comparison_tab = st.tabs(
        ("Evaluación", "Incidencias", "Documentos", "Lista de precios", "Comparación")
    )

    options = {
        f"{supplier.get('name', 'Proveedor')} · {supplier.get('supplier_id', '')}": str(supplier.get("supplier_id", ""))
        for supplier in suppliers
    }

    with evaluation_tab:
        if not options:
            st.info("No hay proveedores registrados.")
        else:
            selected = st.selectbox("Proveedor", tuple(options.keys()), key="supplier_eval_selected")
            supplier_id = options[selected]
            supplier = next(item for item in suppliers if str(item.get("supplier_id", "")) == supplier_id)
            with st.form("supplier_evaluation_form"):
                columns = st.columns(4)
                quality = columns[0].slider("Calidad", 0.0, 5.0, float(_num(supplier.get("quality_score"))), 0.5)
                delivery = columns[1].slider("Cumplimiento", 0.0, 5.0, float(_num(supplier.get("delivery_score"))), 0.5)
                price = columns[2].slider("Precio", 0.0, 5.0, float(_num(supplier.get("price_score"))), 0.5)
                service = columns[3].slider("Atención", 0.0, 5.0, float(_num(supplier.get("service_score"))), 0.5)
                second = st.columns(2)
                preferred_flag = second[0].checkbox("Proveedor preferido", value=bool(supplier.get("preferred")))
                preferred_category = second[1].text_input("Categoría preferida", value=str(supplier.get("preferred_category", "")))
                save_evaluation = st.form_submit_button("Guardar evaluación", type="primary", use_container_width=True)
            if save_evaluation:
                average = (quality + delivery + price + service) / 4
                _update_supplier(supplier_id, {
                    "quality_score": quality,
                    "delivery_score": delivery,
                    "price_score": price,
                    "service_score": service,
                    "rating": average,
                    "preferred": preferred_flag,
                    "preferred_category": preferred_category.strip(),
                    "last_evaluated_at_utc": _now(),
                })
                st.rerun()

            score, level = _score(supplier, events)
            cards = st.columns(3)
            cards[0].metric("Puntaje", f"{score:,.1f}/5")
            cards[1].metric("Riesgo", level)
            cards[2].metric("Preferido", "Sí" if supplier.get("preferred") else "No")

    with incident_tab:
        if not options:
            st.info("No hay proveedores registrados.")
        else:
            with st.form("supplier_incident_form", clear_on_submit=True):
                selected = st.selectbox("Proveedor", tuple(options.keys()), key="supplier_incident_selected")
                columns = st.columns(3)
                incident_type = columns[0].selectbox("Tipo", ("Retraso", "Calidad", "Cantidad", "Precio", "Atención", "Documento", "Otro"))
                severity = columns[1].selectbox("Severidad", ("Baja", "Media", "Alta", "Crítica"))
                responsible = columns[2].text_input("Responsable interno")
                detail = st.text_area("Detalle", max_chars=700)
                submitted = st.form_submit_button("Registrar incidencia", type="primary", use_container_width=True)
            if submitted:
                if not detail.strip():
                    st.error("Describe la incidencia.")
                else:
                    events.append({
                        "event_id": uuid4().hex[:12],
                        "supplier_id": options[selected],
                        "event_type": incident_type,
                        "severity": severity,
                        "detail": detail.strip(),
                        "responsible": responsible.strip() or "Sin asignar",
                        "status": "Abierta",
                        "created_at_utc": _now(),
                    })
                    _save("supplier_events", events)
                    st.rerun()

            for event in reversed(events[-50:]):
                with st.container(border=True):
                    columns = st.columns([3, 1, 1])
                    columns[0].markdown(f"**{_supplier_name(str(event.get('supplier_id', '')), suppliers)} · {event.get('event_type', '')}**")
                    columns[0].write(str(event.get("detail", "")))
                    columns[1].metric("Severidad", str(event.get("severity", "")))
                    columns[2].metric("Estado", str(event.get("status", "Abierta")))
                    if event.get("status") != "Cerrada" and st.button("Cerrar incidencia", key=f"close_supplier_event_{event.get('event_id')}", use_container_width=True):
                        updated = []
                        for current in events:
                            row = dict(current)
                            if row.get("event_id") == event.get("event_id"):
                                row["status"] = "Cerrada"
                                row["closed_at_utc"] = _now()
                            updated.append(row)
                        _save("supplier_events", updated)
                        st.rerun()

    with document_tab:
        if not options:
            st.info("No hay proveedores registrados.")
        else:
            with st.form("supplier_document_form", clear_on_submit=True):
                selected = st.selectbox("Proveedor", tuple(options.keys()), key="supplier_document_selected")
                columns = st.columns(3)
                document_type = columns[0].selectbox("Documento", ("RIF", "Registro mercantil", "Datos bancarios", "Certificado", "Contrato", "Lista de precios", "Otro"))
                reference = columns[1].text_input("Referencia o ubicación")
                expiry = columns[2].date_input("Vencimiento", value=None)
                notes = st.text_input("Notas")
                submitted = st.form_submit_button("Registrar documento", type="primary", use_container_width=True)
            if submitted:
                documents.append({
                    "document_id": uuid4().hex[:12],
                    "supplier_id": options[selected],
                    "document_type": document_type,
                    "reference": reference.strip(),
                    "expiry_date": expiry.isoformat() if expiry else "",
                    "notes": notes.strip(),
                    "created_at_utc": _now(),
                })
                _save("supplier_documents", documents)
                st.rerun()

            for document in reversed(documents[-50:]):
                due = _as_date(document.get("expiry_date"))
                state = "Vencido" if due and due < today else "Vigente" if due else "Sin vencimiento"
                st.write(
                    f"**{_supplier_name(str(document.get('supplier_id', '')), suppliers)} · {document.get('document_type', '')}:** "
                    f"{document.get('reference') or 'Sin referencia'} · {state}"
                )

    with price_tab:
        if not options:
            st.info("No hay proveedores registrados.")
        else:
            with st.form("supplier_price_form", clear_on_submit=True):
                selected = st.selectbox("Proveedor", tuple(options.keys()), key="supplier_price_selected")
                columns = st.columns(4)
                product = columns[0].text_input("Producto o material")
                unit = columns[1].text_input("Unidad", value="unidad")
                unit_price = columns[2].number_input("Precio unitario", min_value=0.0, value=0.0, step=0.1)
                minimum = columns[3].number_input("Compra mínima", min_value=0.0, value=0.0, step=1.0)
                validity = st.date_input("Precio válido hasta", value=None)
                submitted = st.form_submit_button("Registrar precio", type="primary", use_container_width=True)
            if submitted:
                if not product.strip() or unit_price <= 0:
                    st.error("Indica producto y precio válido.")
                else:
                    prices.append({
                        "price_id": uuid4().hex[:12],
                        "supplier_id": options[selected],
                        "product": product.strip(),
                        "unit": unit.strip() or "unidad",
                        "unit_price": float(unit_price),
                        "minimum_quantity": float(minimum),
                        "valid_until": validity.isoformat() if validity else "",
                        "created_at_utc": _now(),
                    })
                    _save("supplier_price_lists", prices)
                    st.rerun()

    with comparison_tab:
        products = sorted({str(item.get("product", "")) for item in prices if item.get("product")})
        if not products:
            st.info("Registra precios para comparar proveedores.")
        else:
            selected_product = st.selectbox("Producto", tuple(products), key="supplier_compare_product")
            matching = [item for item in prices if str(item.get("product", "")) == selected_product]
            for item in sorted(matching, key=lambda row: _num(row.get("unit_price"))):
                supplier = next((row for row in suppliers if str(row.get("supplier_id", "")) == str(item.get("supplier_id", ""))), {})
                score, risk = _score(supplier, events)
                with st.container(border=True):
                    columns = st.columns([3, 1, 1, 1])
                    columns[0].markdown(f"**{supplier.get('name', 'Proveedor')}**")
                    columns[0].caption(f"Compra mínima: {item.get('minimum_quantity', 0)} {item.get('unit', 'unidad')}")
                    columns[1].metric("Precio", format_money(_num(item.get("unit_price"))))
                    columns[2].metric("Puntaje", f"{score:,.1f}/5")
                    columns[3].metric("Riesgo", risk)

    render_info_card(
        "Selección informada",
        "El precio más bajo no siempre es la mejor opción: compara también calidad, cumplimiento, incidencias y condiciones.",
        "GESTIÓN DE PROVEEDORES",
    )
