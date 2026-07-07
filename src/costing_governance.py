"""Gobierno de costos, precios por canal y publicación al catálogo."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, costing_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("costing_versions", "Versiones de costeo"),
        ("costing_price_channels", "Precios por canal"),
        ("costing_variances", "Variaciones de costeo"),
        ("costing_publications", "Publicaciones de precios"),
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


def _margin(price: float, cost: float) -> float:
    return ((price - cost) / price * 100.0) if price > 0 else 0.0


def _minimum_price(cost: float, target_margin: float, fee_percent: float, discount_percent: float) -> float:
    margin = min(max(target_margin / 100.0, 0.0), 0.95)
    fee = min(max(fee_percent / 100.0, 0.0), 0.95)
    discount = min(max(discount_percent / 100.0, 0.0), 0.95)
    denominator = max((1.0 - margin) * (1.0 - fee) * (1.0 - discount), 0.01)
    return cost / denominator


def _product_name(product_id: str, products: list[dict]) -> str:
    for product in products:
        if str(product.get("product_id", "")) == product_id:
            return str(product.get("name", "Producto"))
    return "Producto no disponible"


def _publish_price(product_id: str, price: float, version: dict, approved_by: str) -> None:
    products = _rows("products_registry")
    changed = []
    for product in products:
        row = dict(product)
        if str(row.get("product_id", "")) == product_id:
            row["sale_price"] = float(price)
            row["costing_version_id"] = str(version.get("version_id", ""))
            row["costing_unit_cost"] = _num(version.get("unit_cost"))
            row["price_updated_at_utc"] = _now()
            row["price_updated_by"] = approved_by.strip() or "Sin asignar"
        changed.append(row)
    _save("products_registry", changed)

    publications = _rows("costing_publications")
    publications.append({
        "publication_id": f"PUB-{uuid4().hex[:8].upper()}",
        "version_id": str(version.get("version_id", "")),
        "product_id": product_id,
        "unit_cost": _num(version.get("unit_cost")),
        "published_price": float(price),
        "approved_by": approved_by.strip() or "Sin asignar",
        "created_at_utc": _now(),
    })
    _save("costing_publications", publications)


def _export_versions(rows: list[dict], products: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Versión", "Producto", "Estado", "Costo", "Precio", "Margen", "Vigencia",
        "Revisión", "Preparado por", "Aprobado por", "Motivo",
    ])
    for row in rows:
        writer.writerow([
            row.get("version_id", ""),
            _product_name(str(row.get("product_id", "")), products),
            row.get("status", ""),
            row.get("unit_cost", 0),
            row.get("unit_price", 0),
            row.get("effective_margin", 0),
            row.get("effective_date", ""),
            row.get("review_date", ""),
            row.get("prepared_by", ""),
            row.get("approved_by", ""),
            row.get("reason", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_costing_governance() -> None:
    render_page_header(
        "Costeo",
        "Controla versiones, aprobaciones, precios por canal y publicación segura al catálogo.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_costing_plus()
    finally:
        base.render_page_header = original_header

    products = _rows("products_registry")
    versions = _rows("costing_versions")
    channels = _rows("costing_price_channels")
    variances = _rows("costing_variances")
    publications = _rows("costing_publications")
    currency = get_currency()
    today = date.today()

    pending = [row for row in versions if row.get("status") == "Pendiente"]
    approved = [row for row in versions if row.get("status") == "Aprobada"]
    expired = [
        row for row in approved
        if row.get("review_date") and date.fromisoformat(str(row.get("review_date"))) < today
    ]
    low_margin = [row for row in approved if _num(row.get("effective_margin")) < 20]

    st.divider()
    st.markdown("### Gobierno de costeo")
    metrics = st.columns(5)
    metrics[0].metric("Versiones", str(len(versions)))
    metrics[1].metric("Pendientes", str(len(pending)))
    metrics[2].metric("Aprobadas", str(len(approved)))
    metrics[3].metric("Revisión vencida", str(len(expired)))
    metrics[4].metric("Margen bajo", str(len(low_margin)))

    if expired:
        st.warning(f"Hay {len(expired)} costeo(s) cuya fecha de revisión ya venció.")
    if low_margin:
        st.error(f"Hay {len(low_margin)} versión(es) aprobadas con margen inferior a 20%.")

    version_tab, approval_tab, channel_tab, variance_tab, publication_tab = st.tabs(
        ("Versiones", "Aprobación", "Precios por canal", "Variación real", "Publicación")
    )

    product_options = {
        f"{product.get('name', 'Producto')} · {product.get('product_id', '')}": str(product.get("product_id", ""))
        for product in products
    }

    with version_tab:
        latest = st.session_state.get("advanced_costing_result")
        if not isinstance(latest, dict):
            st.info("Primero calcula un costeo completo en la calculadora avanzada.")
        elif not product_options:
            st.info("No hay productos en el catálogo para vincular el costeo.")
        else:
            with st.form("costing_version_form", clear_on_submit=True):
                selected = st.selectbox("Producto", tuple(product_options.keys()))
                product_id = product_options[selected]
                columns = st.columns(4)
                prepared_by = columns[0].text_input("Preparado por")
                effective_date = columns[1].date_input("Vigencia desde", value=today)
                review_date = columns[2].date_input("Revisar el", value=today + timedelta(days=90))
                reason = columns[3].text_input("Motivo de la versión")
                submitted = st.form_submit_button("Crear versión pendiente", type="primary", use_container_width=True)
            if submitted:
                if not prepared_by.strip() or not reason.strip():
                    st.error("Preparado por y motivo son obligatorios.")
                elif review_date < effective_date:
                    st.error("La fecha de revisión no puede ser anterior a la vigencia.")
                else:
                    product_versions = [row for row in versions if str(row.get("product_id", "")) == product_id]
                    version_number = len(product_versions) + 1
                    versions.append({
                        "version_id": f"CSTV-{uuid4().hex[:8].upper()}",
                        "version_number": version_number,
                        "product_id": product_id,
                        "unit_cost": _num(latest.get("unit_cost")),
                        "unit_price": _num(latest.get("unit_price")),
                        "effective_margin": _num(latest.get("effective_margin")),
                        "currency": str(latest.get("currency", currency)),
                        "pricing_method": str(latest.get("pricing_method", "")),
                        "target_percent": _num(latest.get("target_percent")),
                        "effective_date": effective_date.isoformat(),
                        "review_date": review_date.isoformat(),
                        "prepared_by": prepared_by.strip(),
                        "reason": reason.strip(),
                        "status": "Pendiente",
                        "created_at_utc": _now(),
                    })
                    _save("costing_versions", versions)
                    st.rerun()

        st.download_button(
            "Descargar versiones CSV",
            data=_export_versions(versions, products),
            file_name=f"versiones_costeo_{today.isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not versions,
        )

        for row in reversed(versions[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{_product_name(str(row.get('product_id', '')), products)} · v{row.get('version_number', '')}**")
                cols[0].caption(f"{row.get('version_id', '')} · {row.get('reason', '')}")
                cols[1].metric("Costo", format_money(_num(row.get("unit_cost")), currency))
                cols[2].metric("Precio", format_money(_num(row.get("unit_price")), currency))
                cols[3].metric("Estado", str(row.get("status", "")))

    with approval_tab:
        if not pending:
            st.info("No hay versiones pendientes de aprobación.")
        for row in reversed(pending):
            with st.container(border=True):
                st.markdown(f"**{_product_name(str(row.get('product_id', '')), products)} · versión {row.get('version_number', '')}**")
                cols = st.columns(3)
                cols[0].metric("Costo", format_money(_num(row.get("unit_cost")), currency))
                cols[1].metric("Precio", format_money(_num(row.get("unit_price")), currency))
                cols[2].metric("Margen", f"{_num(row.get('effective_margin')):,.1f}%")
                with st.form(f"approve_costing_{row.get('version_id')}"):
                    decision = st.selectbox("Decisión", ("Aprobar", "Rechazar"), key=f"decision_{row.get('version_id')}")
                    approved_by = st.text_input("Responsable", key=f"approver_{row.get('version_id')}")
                    note = st.text_area("Nota", max_chars=400, key=f"approval_note_{row.get('version_id')}")
                    submitted = st.form_submit_button("Guardar decisión", type="primary", use_container_width=True)
                if submitted:
                    if not approved_by.strip():
                        st.error("Indica responsable de la decisión.")
                    else:
                        changed = []
                        for current in versions:
                            item = dict(current)
                            if item.get("version_id") == row.get("version_id"):
                                item["status"] = "Aprobada" if decision == "Aprobar" else "Rechazada"
                                item["approved_by"] = approved_by.strip() if decision == "Aprobar" else ""
                                item["rejected_by"] = approved_by.strip() if decision == "Rechazar" else ""
                                item["approval_note"] = note.strip()
                                item["decision_at_utc"] = _now()
                            changed.append(item)
                        _save("costing_versions", changed)
                        st.rerun()

    with channel_tab:
        approved_options = {
            f"{_product_name(str(row.get('product_id', '')), products)} · v{row.get('version_number', '')}": row
            for row in approved
        }
        if not approved_options:
            st.info("Aprueba una versión antes de calcular precios por canal.")
        else:
            selected = st.selectbox("Versión aprobada", tuple(approved_options.keys()))
            version = approved_options[selected]
            with st.form("costing_channel_form", clear_on_submit=True):
                columns = st.columns(4)
                channel_name = columns[0].text_input("Canal", placeholder="Efectivo, tarjeta, marketplace, mayorista")
                fee_percent = columns[1].number_input("Comisión del canal %", min_value=0.0, max_value=95.0, value=0.0, step=0.5)
                discount_percent = columns[2].number_input("Descuento máximo %", min_value=0.0, max_value=95.0, value=0.0, step=0.5)
                target_margin = columns[3].number_input("Margen mínimo %", min_value=0.0, max_value=95.0, value=max(_num(version.get("effective_margin")), 20.0), step=1.0)
                submitted = st.form_submit_button("Guardar precio del canal", type="primary", use_container_width=True)
            if submitted:
                if not channel_name.strip():
                    st.error("Indica el nombre del canal.")
                else:
                    minimum = _minimum_price(_num(version.get("unit_cost")), float(target_margin), float(fee_percent), float(discount_percent))
                    channels.append({
                        "channel_id": f"CH-{uuid4().hex[:8].upper()}",
                        "version_id": str(version.get("version_id", "")),
                        "product_id": str(version.get("product_id", "")),
                        "channel_name": channel_name.strip(),
                        "fee_percent": float(fee_percent),
                        "discount_percent": float(discount_percent),
                        "target_margin": float(target_margin),
                        "minimum_price": minimum,
                        "created_at_utc": _now(),
                    })
                    _save("costing_price_channels", channels)
                    st.rerun()

        for row in reversed(channels[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{_product_name(str(row.get('product_id', '')), products)} · {row.get('channel_name', '')}**")
                cols[1].metric("Precio mínimo", format_money(_num(row.get("minimum_price")), currency))
                cols[2].metric("Comisión", f"{_num(row.get('fee_percent')):,.1f}%")
                cols[3].metric("Descuento", f"{_num(row.get('discount_percent')):,.1f}%")

    with variance_tab:
        approved_options = {
            f"{_product_name(str(row.get('product_id', '')), products)} · v{row.get('version_number', '')}": row
            for row in approved
        }
        if not approved_options:
            st.info("No hay versiones aprobadas para comparar.")
        else:
            selected = st.selectbox("Costeo estándar", tuple(approved_options.keys()), key="variance_version")
            version = approved_options[selected]
            with st.form("costing_variance_form", clear_on_submit=True):
                columns = st.columns(4)
                actual_cost = columns[0].number_input("Costo real unitario", min_value=0.0, value=_num(version.get("unit_cost")), step=0.01)
                actual_quantity = columns[1].number_input("Cantidad real", min_value=1, value=1, step=1)
                responsible = columns[2].text_input("Responsable")
                reference = columns[3].text_input("Referencia de producción")
                note = st.text_area("Observación", max_chars=500)
                submitted = st.form_submit_button("Registrar variación", type="primary", use_container_width=True)
            if submitted:
                standard = _num(version.get("unit_cost"))
                variance = float(actual_cost) - standard
                variance_percent = variance / standard * 100.0 if standard > 0 else 0.0
                variances.append({
                    "variance_id": f"VAR-{uuid4().hex[:8].upper()}",
                    "version_id": str(version.get("version_id", "")),
                    "product_id": str(version.get("product_id", "")),
                    "standard_cost": standard,
                    "actual_cost": float(actual_cost),
                    "quantity": int(actual_quantity),
                    "variance": variance,
                    "variance_percent": variance_percent,
                    "total_impact": variance * int(actual_quantity),
                    "responsible": responsible.strip() or "Sin asignar",
                    "reference": reference.strip(),
                    "note": note.strip(),
                    "created_at_utc": _now(),
                })
                _save("costing_variances", variances)
                st.rerun()

        for row in reversed(variances[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{_product_name(str(row.get('product_id', '')), products)} · {row.get('reference') or row.get('variance_id', '')}**")
                cols[1].metric("Variación", format_money(_num(row.get("variance")), currency))
                cols[2].metric("Variación %", f"{_num(row.get('variance_percent')):+,.1f}%")
                cols[3].metric("Impacto total", format_money(_num(row.get("total_impact")), currency))
                if abs(_num(row.get("variance_percent"))) >= 10:
                    st.warning("La desviación supera 10%. Conviene revisar receta, desperdicio, proveedor o tiempo de producción.")

    with publication_tab:
        if not approved:
            st.info("No hay versiones aprobadas para publicar.")
        else:
            options = {
                f"{_product_name(str(row.get('product_id', '')), products)} · v{row.get('version_number', '')}": row
                for row in approved
            }
            selected = st.selectbox("Versión", tuple(options.keys()), key="publication_version")
            version = options[selected]
            channel_rows = [row for row in channels if row.get("version_id") == version.get("version_id")]
            price_options = {"Precio aprobado": _num(version.get("unit_price"))}
            for row in channel_rows:
                price_options[f"Canal: {row.get('channel_name', '')}"] = _num(row.get("minimum_price"))
            selected_price_label = st.selectbox("Precio a publicar", tuple(price_options.keys()))
            selected_price = price_options[selected_price_label]
            approved_by = st.text_input("Responsable de publicación")
            st.metric("Precio seleccionado", format_money(selected_price, currency))
            if st.button("Publicar en catálogo", type="primary", use_container_width=True):
                if not approved_by.strip():
                    st.error("Indica responsable de publicación.")
                else:
                    _publish_price(str(version.get("product_id", "")), selected_price, version, approved_by)
                    st.success("Precio publicado en el catálogo.")
                    st.rerun()

        if publications:
            st.markdown("#### Historial de publicaciones")
        for row in reversed(publications[-100:]):
            st.write(
                f"**{_product_name(str(row.get('product_id', '')), products)}** · "
                f"{format_money(_num(row.get('published_price')), currency)} · "
                f"{row.get('approved_by', '')} · {row.get('created_at_utc', '')}"
            )

    render_info_card(
        "Costo controlado",
        "Las versiones aprobadas separan cálculo, decisión y publicación para evitar cambios de precio sin trazabilidad.",
        "GOBIERNO DE RENTABILIDAD",
    )


app_shell.FUNCTIONAL_MODULES["Costeo"] = render_costing_governance
