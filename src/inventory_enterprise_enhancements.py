"""Mejoras de registro y consulta para el inventario empresarial.

Se activan por monkeypatch para mantener el módulo principal estable y permitir
que la pantalla real de Inventario muestre dimensiones, cm² y m².
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import streamlit as st

from src.money import format_money


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _content_inputs(prefix: str, module) -> dict:
    """Captura medidas físicas y calcula área en tiempo real."""
    content_type = st.selectbox(
        "¿Cómo se mide el contenido de cada unidad?",
        module.CONTENT_TYPES,
        key=f"{prefix}_content_type",
        help="Elige Área para papeles, vinilos, láminas, foami y materiales que se consumen por superficie.",
    )
    if content_type == module.CONTENT_TYPES[1]:
        a, b = st.columns(2)
        width_cm = a.number_input(
            "Ancho (cm)", min_value=0.0, value=0.0, step=0.1,
            format="%.2f", key=f"{prefix}_width",
        )
        height_cm = b.number_input(
            "Largo / alto (cm)", min_value=0.0, value=0.0, step=0.1,
            format="%.2f", key=f"{prefix}_height",
        )
        area_cm2 = round(float(width_cm) * float(height_cm), 4)
        area_m2 = area_cm2 / 10_000
        result = st.columns(2)
        result[0].metric("Área por unidad", f"{area_cm2:,.2f} cm²")
        result[1].metric("Equivalente", f"{area_m2:,.6f} m²")
        st.caption("Cálculo automático: ancho × largo. No tienes que escribir los cm² manualmente.")
        return {
            "content_type": "area",
            "content_value": area_cm2,
            "content_unit": "cm²",
            "width_cm": float(width_cm),
            "height_cm": float(height_cm),
            "area_cm2": area_cm2,
            "area_m2": area_m2,
        }
    if content_type == module.CONTENT_TYPES[2]:
        weight_g = st.number_input("Peso por unidad (g)", min_value=0.0, value=0.0, step=0.1, key=f"{prefix}_weight")
        return {"content_type": "weight", "content_value": float(weight_g), "content_unit": "g"}
    if content_type == module.CONTENT_TYPES[3]:
        volume_ml = st.number_input("Volumen por unidad (ml)", min_value=0.0, value=0.0, step=1.0, key=f"{prefix}_volume")
        return {"content_type": "volume", "content_value": float(volume_ml), "content_unit": "ml"}
    return {"content_type": "piece", "content_value": 0.0, "content_unit": ""}


def _register(rows: list[dict], module) -> None:
    st.caption("Registra el material, su existencia inicial, su costo real y las dimensiones que usa Producción y Costeo.")
    with st.form("enterprise_inventory_item", clear_on_submit=True):
        a, b, c, d = st.columns(4)
        sku = a.text_input("SKU / código")
        name = b.text_input("Nombre del material *")
        category = c.selectbox("Categoría", module.CATEGORIES)
        unit = d.selectbox("Unidad de control", module.UNITS)

        a, b, c = st.columns(3)
        quantity = a.number_input("Existencia inicial", min_value=0.0, value=0.0, step=1.0)
        minimum = b.number_input("Stock mínimo", min_value=0.0, value=0.0, step=1.0)
        maximum = c.number_input("Stock máximo", min_value=0.0, value=0.0, step=1.0)

        st.markdown("##### Costo real de adquisición")
        purchase = module._purchase_inputs("reg")

        st.markdown("##### Medida física por unidad")
        content = _content_inputs("reg", module)

        a, b, c = st.columns(3)
        location = a.text_input("Ubicación", value="Almacén principal")
        lot = b.text_input("Lote")
        expiry = c.date_input("Vencimiento", value=None)
        submit = st.form_submit_button("Registrar artículo", type="primary", use_container_width=True)

    if not submit:
        return
    if not name.strip():
        st.error("El nombre del material es obligatorio.")
        return
    if purchase["material_subtotal"] <= 0:
        st.error("El costo del material debe ser mayor que cero.")
        return
    if maximum > 0 and minimum > maximum:
        st.error("El stock mínimo no puede ser mayor que el stock máximo.")
        return
    if content["content_type"] == "area" and (content.get("width_cm", 0) <= 0 or content.get("height_cm", 0) <= 0):
        st.error("Para materiales medidos por área debes completar ancho y largo.")
        return

    item_id = sku.strip() or uuid4().hex[:8].upper()
    if any(str(r.get("item_id")) == item_id or (sku.strip() and str(r.get("sku")) == sku.strip()) for r in rows):
        st.error("El SKU o ID ya existe.")
        return

    unit_cost, landed_total = module._landed_unit_cost(
        purchase["material_subtotal"], purchase["shipping_cost"], purchase["tax_amount"],
        purchase["exchange_rate"], max(quantity, 1),
    )
    item = {
        "item_id": item_id,
        "sku": sku.strip(),
        "name": name.strip(),
        "category": category,
        "unit_name": unit,
        "available_quantity": 0.0,
        "minimum_stock": float(minimum),
        "maximum_stock": float(maximum),
        "unit_cost": unit_cost,
        "purchase_cost": landed_total,
        "purchased_quantity": float(max(quantity, 1)),
        "supplier": purchase["supplier"],
        "location": location.strip(),
        "lot": lot.strip(),
        "expiry_date": expiry.isoformat() if expiry else "",
        "active": True,
        "created_at_utc": module._now(),
        "purchase_currency": purchase["currency"],
        "exchange_rate_used": purchase["exchange_rate"],
        "payment_method": purchase["payment_method"],
        "content_type": content["content_type"],
        "content_value": content["content_value"],
        "content_unit": content["content_unit"],
        "width_cm": content.get("width_cm", 0.0),
        "height_cm": content.get("height_cm", 0.0),
        "area_cm2": content.get("area_cm2", 0.0),
        "area_m2": content.get("area_m2", 0.0),
    }
    rows.append(item)
    module._save(rows)
    if quantity > 0:
        module._movement(item, "Entrada", float(quantity), "Existencia inicial", unit_cost, purchase_detail=purchase)
        module._save(rows)
    st.success(
        f"Artículo registrado. Costo unitario real: {format_money(unit_cost)}"
        + (f" · Área por unidad: {content['area_cm2']:,.2f} cm²" if content["content_type"] == "area" else "")
    )
    st.rerun()


def _dimension_text(row: dict) -> str:
    content_type = row.get("content_type")
    if content_type == "area":
        width = _num(row.get("width_cm"))
        height = _num(row.get("height_cm"))
        area = _num(row.get("area_cm2"), _num(row.get("content_value")))
        if width > 0 and height > 0:
            return f"{width:,.2f} × {height:,.2f} cm · {area:,.2f} cm²"
        return f"{area:,.2f} cm²" if area > 0 else "Área sin medidas"
    if content_type == "volume":
        return f"{_num(row.get('content_value')):,.2f} ml"
    if content_type == "weight":
        return f"{_num(row.get('content_value')):,.2f} g"
    return "Pieza completa"


def _catalog(rows: list[dict], module) -> None:
    st.caption("Consulta existencias, costos, dimensiones y estado de reposición desde una sola tabla.")
    a, b, c = st.columns([2, 1, 1])
    query = a.text_input("Buscar por nombre, SKU, lote o proveedor")
    category = b.selectbox("Filtrar categoría", ("Todas", *module.CATEGORIES))
    status = c.selectbox("Estado", ("Todos", "Disponible", "Stock bajo", "Agotado", "Inactivo"))

    table = []
    for row in rows:
        haystack = f"{row.get('name','')} {row.get('sku','')} {row.get('item_id','')} {row.get('lot','')} {row.get('supplier','')}".casefold()
        if query and query.casefold() not in haystack:
            continue
        if category != "Todas" and row.get("category") != category:
            continue
        stock = _num(row.get("available_quantity"))
        minimum = _num(row.get("minimum_stock"))
        low = minimum > 0 and stock <= minimum
        current = "Inactivo" if not row.get("active", True) else "Agotado" if stock <= 0 else "Stock bajo" if low else "Disponible"
        if status != "Todos" and current != status:
            continue
        unit_cost = _num(row.get("unit_cost"))
        table.append({
            "SKU": row.get("sku") or row.get("item_id"),
            "Material": row.get("name"),
            "Categoría": row.get("category"),
            "Existencia": round(stock, 4),
            "Unidad": row.get("unit_name"),
            "Dimensión / contenido": _dimension_text(row),
            "Costo unitario": round(unit_cost, 4),
            "Valor disponible": round(stock * unit_cost, 2),
            "Mínimo": round(minimum, 4),
            "Máximo": round(_num(row.get("maximum_stock")), 4),
            "Estado": current,
            "Proveedor": row.get("supplier", ""),
            "Ubicación": row.get("location", ""),
        })

    if not table:
        st.info("No hay artículos que coincidan con los filtros.")
        return
    st.dataframe(table, use_container_width=True, hide_index=True)
    metrics = st.columns(4)
    metrics[0].metric("Resultados", len(table))
    metrics[1].metric("Unidades disponibles", f"{sum(_num(r['Existencia']) for r in table):,.2f}")
    metrics[2].metric("Valor filtrado", format_money(sum(_num(r['Valor disponible']) for r in table)))
    metrics[3].metric("Con stock bajo", sum(1 for r in table if r["Estado"] in {"Stock bajo", "Agotado"}))


def activate_inventory_enterprise_enhancements(module) -> None:
    """Sustituye únicamente las vistas de registro y catálogo."""
    module._register = lambda rows: _register(rows, module)
    module._catalog = lambda rows: _catalog(rows, module)
