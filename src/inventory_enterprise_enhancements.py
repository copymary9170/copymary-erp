"""Mejoras de registro y consulta para el inventario empresarial.

La vista de registro permite medir materiales rectangulares incluso cuando el
corte no es perfectamente uniforme. Se guardan los cuatro lados, el área
estimada y el área utilizable conservadora para Producción y Costeo.
"""
from __future__ import annotations

from uuid import uuid4

import streamlit as st

from src.money import format_money


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _area_measurements(prefix: str) -> dict:
    """Captura los cuatro lados y calcula áreas para cortes regulares o irregulares."""
    st.caption(
        "Mide cada borde por separado. Esto permite registrar hojas, vinilos o láminas "
        "que no quedaron cortados exactamente iguales."
    )
    width_columns = st.columns(2)
    width_top_cm = width_columns[0].number_input(
        "Ancho superior (cm)", min_value=0.0, value=0.0, step=0.01,
        format="%.2f", key=f"{prefix}_width_top",
    )
    width_bottom_cm = width_columns[1].number_input(
        "Ancho inferior (cm)", min_value=0.0, value=0.0, step=0.01,
        format="%.2f", key=f"{prefix}_width_bottom",
    )
    height_columns = st.columns(2)
    height_left_cm = height_columns[0].number_input(
        "Alto izquierdo (cm)", min_value=0.0, value=0.0, step=0.01,
        format="%.2f", key=f"{prefix}_height_left",
    )
    height_right_cm = height_columns[1].number_input(
        "Alto derecho (cm)", min_value=0.0, value=0.0, step=0.01,
        format="%.2f", key=f"{prefix}_height_right",
    )

    values = (width_top_cm, width_bottom_cm, height_left_cm, height_right_cm)
    complete = all(value > 0 for value in values)
    average_width_cm = (float(width_top_cm) + float(width_bottom_cm)) / 2 if complete else 0.0
    average_height_cm = (float(height_left_cm) + float(height_right_cm)) / 2 if complete else 0.0
    estimated_area_cm2 = average_width_cm * average_height_cm if complete else 0.0
    usable_width_cm = min(float(width_top_cm), float(width_bottom_cm)) if complete else 0.0
    usable_height_cm = min(float(height_left_cm), float(height_right_cm)) if complete else 0.0
    usable_area_cm2 = usable_width_cm * usable_height_cm if complete else 0.0
    area_m2 = usable_area_cm2 / 10_000
    width_difference_cm = abs(float(width_top_cm) - float(width_bottom_cm)) if complete else 0.0
    height_difference_cm = abs(float(height_left_cm) - float(height_right_cm)) if complete else 0.0
    maximum_difference_cm = max(width_difference_cm, height_difference_cm)
    cut_status = "Corte irregular" if maximum_difference_cm > 0.20 else "Corte regular"

    if complete:
        metrics = st.columns(4)
        metrics[0].metric("Ancho promedio", f"{average_width_cm:,.2f} cm")
        metrics[1].metric("Alto promedio", f"{average_height_cm:,.2f} cm")
        metrics[2].metric("Área estimada", f"{estimated_area_cm2:,.2f} cm²")
        metrics[3].metric("Área utilizable", f"{usable_area_cm2:,.2f} cm²")
        st.caption(
            f"Producción y Costeo usarán el área utilizable conservadora: "
            f"{usable_area_cm2:,.2f} cm² ({area_m2:,.6f} m²)."
        )
        if cut_status == "Corte irregular":
            st.warning(
                f"Se detectó diferencia de corte de hasta {maximum_difference_cm:,.2f} cm. "
                "El sistema usará los lados más pequeños para no sobreestimar el material disponible."
            )
        else:
            st.success("Las diferencias entre lados están dentro de la tolerancia de 0,20 cm.")
    elif any(value > 0 for value in values):
        st.info("Completa las cuatro medidas para calcular correctamente los cm².")

    return {
        "content_type": "area",
        "content_value": usable_area_cm2,
        "content_unit": "cm²",
        "width_cm": average_width_cm,
        "height_cm": average_height_cm,
        "width_top_cm": float(width_top_cm),
        "width_bottom_cm": float(width_bottom_cm),
        "height_left_cm": float(height_left_cm),
        "height_right_cm": float(height_right_cm),
        "average_width_cm": average_width_cm,
        "average_height_cm": average_height_cm,
        "estimated_area_cm2": estimated_area_cm2,
        "usable_area_cm2": usable_area_cm2,
        "area_cm2": usable_area_cm2,
        "area_m2": area_m2,
        "width_difference_cm": width_difference_cm,
        "height_difference_cm": height_difference_cm,
        "maximum_difference_cm": maximum_difference_cm,
        "cut_status": cut_status if complete else "Sin medir",
        "measurements_complete": complete,
    }


def _content_inputs(prefix: str, module, content_type: str) -> dict:
    """Muestra las medidas de acuerdo con el tipo seleccionado fuera del formulario."""
    if content_type == module.CONTENT_TYPES[1]:
        return _area_measurements(prefix)
    if content_type == module.CONTENT_TYPES[2]:
        weight_g = st.number_input(
            "Peso por unidad (g)", min_value=0.0, value=0.0, step=0.1,
            key=f"{prefix}_weight",
        )
        return {"content_type": "weight", "content_value": float(weight_g), "content_unit": "g"}
    if content_type == module.CONTENT_TYPES[3]:
        volume_ml = st.number_input(
            "Volumen por unidad (ml)", min_value=0.0, value=0.0, step=1.0,
            key=f"{prefix}_volume",
        )
        return {"content_type": "volume", "content_value": float(volume_ml), "content_unit": "ml"}
    return {"content_type": "piece", "content_value": 0.0, "content_unit": ""}


def _register(rows: list[dict], module) -> None:
    st.caption("Registra el material, su existencia inicial, su costo real y las medidas que usa Producción y Costeo.")

    with st.container(border=True):
        a, b, c, d = st.columns(4)
        sku = a.text_input("SKU / código", key="reg_sku")
        name = b.text_input("Nombre del material *", key="reg_name")
        category = c.selectbox("Categoría", module.CATEGORIES, key="reg_category")
        unit = d.selectbox("Unidad de control", module.UNITS, key="reg_unit")

        a, b, c = st.columns(3)
        quantity = a.number_input("Existencia inicial", min_value=0.0, value=0.0, step=1.0, key="reg_quantity")
        minimum = b.number_input("Stock mínimo", min_value=0.0, value=0.0, step=1.0, key="reg_minimum")
        maximum = c.number_input("Stock máximo", min_value=0.0, value=0.0, step=1.0, key="reg_maximum")

        st.markdown("##### Costo real de adquisición")
        purchase = module._purchase_inputs("reg")

        st.markdown("##### Medida física por unidad")
        content_type = st.selectbox(
            "¿Cómo se mide el contenido de cada unidad?",
            module.CONTENT_TYPES,
            key="reg_content_type_selector",
            help="Elige Área para papeles, vinilos, láminas, foami y materiales consumidos por superficie.",
        )
        content = _content_inputs("reg", module, content_type)

        a, b, c = st.columns(3)
        location = a.text_input("Ubicación", value="Almacén principal", key="reg_location")
        lot = b.text_input("Lote", key="reg_lot")
        expiry = c.date_input("Vencimiento", value=None, key="reg_expiry")
        notes = st.text_area(
            "Observaciones del material",
            placeholder="Ejemplo: lote cortado irregularmente, bordes dañados, reservar para trabajos pequeños...",
            key="reg_inventory_notes",
        )
        submit = st.button("Registrar artículo", type="primary", use_container_width=True, key="reg_submit")

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
    if content["content_type"] == "area" and not content.get("measurements_complete", False):
        st.error("Para materiales medidos por área debes completar los cuatro lados.")
        return

    item_id = sku.strip() or uuid4().hex[:8].upper()
    if any(str(row.get("item_id")) == item_id or (sku.strip() and str(row.get("sku")) == sku.strip()) for row in rows):
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
        "notes": notes.strip(),
        "active": True,
        "created_at_utc": module._now(),
        "purchase_currency": purchase["currency"],
        "exchange_rate_used": purchase["exchange_rate"],
        "payment_method": purchase["payment_method"],
        **content,
    }
    item.pop("measurements_complete", None)
    rows.append(item)
    module._save(rows)
    if quantity > 0:
        module._movement(item, "Entrada", float(quantity), "Existencia inicial", unit_cost, purchase_detail=purchase)
        module._save(rows)

    message = f"Artículo registrado. Costo unitario real: {format_money(unit_cost)}"
    if content["content_type"] == "area":
        message += (
            f" · Área utilizable por unidad: {content['usable_area_cm2']:,.2f} cm²"
            f" · {content['cut_status']}"
        )
    st.success(message)
    st.rerun()


def _dimension_text(row: dict) -> str:
    content_type = row.get("content_type")
    if content_type == "area":
        top = _num(row.get("width_top_cm"))
        bottom = _num(row.get("width_bottom_cm"))
        left = _num(row.get("height_left_cm"))
        right = _num(row.get("height_right_cm"))
        usable = _num(row.get("usable_area_cm2"), _num(row.get("area_cm2"), _num(row.get("content_value"))))
        if all(value > 0 for value in (top, bottom, left, right)):
            return (
                f"Anchos {top:,.2f}/{bottom:,.2f} cm · "
                f"Altos {left:,.2f}/{right:,.2f} cm · útil {usable:,.2f} cm²"
            )
        width = _num(row.get("width_cm"))
        height = _num(row.get("height_cm"))
        if width > 0 and height > 0:
            return f"{width:,.2f} × {height:,.2f} cm · {usable:,.2f} cm²"
        return f"{usable:,.2f} cm²" if usable > 0 else "Área sin medidas"
    if content_type == "volume":
        return f"{_num(row.get('content_value')):,.2f} ml"
    if content_type == "weight":
        return f"{_num(row.get('content_value')):,.2f} g"
    return "Pieza completa"


def _catalog(rows: list[dict], module) -> None:
    st.caption("Consulta existencias, costos, medidas reales y estado de reposición desde una sola tabla.")
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
            "Medidas reales": _dimension_text(row),
            "Calidad de corte": row.get("cut_status", "No evaluada"),
            "Costo unitario": round(unit_cost, 4),
            "Valor disponible": round(stock * unit_cost, 2),
            "Mínimo": round(minimum, 4),
            "Máximo": round(_num(row.get("maximum_stock")), 4),
            "Estado": current,
            "Proveedor": row.get("supplier", ""),
            "Ubicación": row.get("location", ""),
            "Observaciones": row.get("notes", ""),
        })

    if not table:
        st.info("No hay artículos que coincidan con los filtros.")
        return
    st.dataframe(table, use_container_width=True, hide_index=True)
    metrics = st.columns(5)
    metrics[0].metric("Resultados", len(table))
    metrics[1].metric("Unidades disponibles", f"{sum(_num(row['Existencia']) for row in table):,.2f}")
    metrics[2].metric("Valor filtrado", format_money(sum(_num(row['Valor disponible']) for row in table)))
    metrics[3].metric("Con stock bajo", sum(1 for row in table if row["Estado"] in {"Stock bajo", "Agotado"}))
    metrics[4].metric("Corte irregular", sum(1 for row in table if row["Calidad de corte"] == "Corte irregular"))


def activate_inventory_enterprise_enhancements(module) -> None:
    """Sustituye únicamente las vistas de registro y catálogo."""
    module._register = lambda rows: _register(rows, module)
    module._catalog = lambda rows: _catalog(rows, module)
