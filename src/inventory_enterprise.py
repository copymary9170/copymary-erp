"""Inventario empresarial para CopyMary ERP.

Mantiene compatibilidad con ``inventory_registry`` y ``inventory_movements``.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from io import StringIO
from uuid import uuid4
import math
import streamlit as st

from src.components import render_info_card, render_page_header
from src.erp_database import latest_exchange_rate
from src.money import format_money, get_currency
from src.session_utils import read_list, save_list

CSV_COLUMNS = (
    "item_id", "sku", "name", "category", "available_quantity", "unit_name",
    "unit_cost", "minimum_stock", "maximum_stock", "supplier", "location", "lot", "expiry_date",
    "purchase_currency", "content_type", "content_value", "content_unit",
)

CURRENCIES = ("USD", "VES", "EUR")
PAYMENT_METHODS = ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Tarjeta", "Crédito de proveedor", "Otro")
CONTENT_TYPES = ("Pieza completa (sin medida)", "Área (cm²)", "Peso (g)", "Volumen (ml)")

CATEGORIES = (
    "Papel y cartulina", "Tintas y botellas", "Cartuchos", "Tóner",
    "Sublimación", "Corte y Cameo", "Plastificación", "Papelería",
    "Empaque", "Repuestos", "Producto terminado", "Otro",
)
UNITS = ("unidad", "hoja", "paquete", "resma", "ml", "litro", "metro", "cm", "rollo", "pliego", "kg")
MOVEMENTS = ("Entrada", "Salida", "Ajuste positivo", "Ajuste negativo", "Merma", "Devolución")


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_exchange_rate(currency: str, base_currency: str) -> float:
    if currency == base_currency:
        return 1.0
    looked_up = latest_exchange_rate(currency, base_currency)
    return _num(looked_up.get("rate"), 1.0) if looked_up else 1.0


def _landed_unit_cost(subtotal: float, shipping: float, tax: float, exchange_rate: float, quantity: float) -> tuple[float, float]:
    """Convierte costo del material + envío + impuestos (en la moneda de
    compra) a la moneda base del ERP, usando la tasa de cambio indicada, y
    devuelve `(costo_unitario_base, total_landed_base)`.
    """
    total_purchase_currency = subtotal + shipping + tax
    total_base = total_purchase_currency / max(exchange_rate, 0.0001)
    unit_cost = total_base / max(quantity, 1.0)
    return unit_cost, total_base


def allocate_shared_costs(line_subtotals: list[float], shipping: float, tax: float) -> list[tuple[float, float]]:
    """Reparte el envío y los impuestos de UNA factura entre varias líneas de
    compra, proporcional al subtotal de cada línea — el mismo criterio que ya
    usa el registro de un solo artículo (`_landed_unit_cost`), aplicado ahora
    a una factura con varios artículos que comparten un mismo flete y un
    mismo impuesto.

    Quien compró más en la factura absorbe más del flete y el impuesto,
    en vez de que cada línea tenga que adivinar cuánto le toca. Si todas las
    líneas suman 0 (por ejemplo, artículos sin precio aún), reparte en partes
    iguales para no dividir entre cero.

    Devuelve una lista paralela de `(envío_asignado, impuesto_asignado)`.
    """
    count = len(line_subtotals)
    if count == 0:
        return []
    total = sum(line_subtotals)
    if total <= 0:
        return [(shipping / count, tax / count) for _ in line_subtotals]
    return [(shipping * (subtotal / total), tax * (subtotal / total)) for subtotal in line_subtotals]


def _purchase_inputs(prefix: str, *, default_supplier: str = "") -> dict:
    """Campos compartidos de "cómo se adquirió este material": proveedor,
    moneda, tasa de cambio usada, método de pago, costo del material, envío
    y impuestos. Se usa tanto al registrar un artículo nuevo (existencia
    inicial) como al registrar cada "Entrada" posterior, para que el costo
    unitario siempre refleje lo que realmente costó traer el material al
    negocio, no solo el precio de lista.
    """
    base_currency = get_currency()
    a, b, c = st.columns(3)
    currency = a.selectbox("Moneda de la compra", CURRENCIES, index=CURRENCIES.index(base_currency) if base_currency in CURRENCIES else 0, key=f"{prefix}_currency")
    same_currency = currency == base_currency
    exchange_rate = b.number_input(
        f"Tasa de cambio usada (1 {base_currency} = ? {currency})",
        min_value=0.0001, value=1.0 if same_currency else _default_exchange_rate(currency, base_currency),
        step=0.01, format="%.4f", disabled=same_currency, key=f"{prefix}_rate",
    )
    payment_method = c.selectbox("Método de pago", PAYMENT_METHODS, key=f"{prefix}_payment")
    a, b, c = st.columns(3)
    material_subtotal = a.number_input(f"Costo del material ({currency})", min_value=0.0, value=0.0, step=1.0, format="%.4f", key=f"{prefix}_subtotal")
    shipping_cost = b.number_input(f"Envío / flete ({currency})", min_value=0.0, value=0.0, step=1.0, format="%.2f", key=f"{prefix}_shipping")
    tax_amount = c.number_input(f"Impuestos ({currency})", min_value=0.0, value=0.0, step=1.0, format="%.2f", key=f"{prefix}_tax")
    supplier = st.text_input("Proveedor", value=default_supplier, key=f"{prefix}_supplier")
    return {
        "currency": currency, "same_currency": same_currency, "exchange_rate": 1.0 if same_currency else float(exchange_rate),
        "payment_method": payment_method, "material_subtotal": float(material_subtotal),
        "shipping_cost": float(shipping_cost), "tax_amount": float(tax_amount), "supplier": supplier.strip(),
    }


def _content_inputs(prefix: str) -> dict:
    """Contenido físico de cada unidad (cm², g o ml), para poder calcular
    merma más adelante en Plastificado, Corte en Cameo y Sublimado. Es una
    propiedad del material (no de cada compra), por eso solo se pide al
    registrar el artículo.
    """
    content_type = st.selectbox("¿Cómo se mide el contenido de cada unidad? (para calcular merma después)", CONTENT_TYPES, key=f"{prefix}_content_type")
    if content_type == CONTENT_TYPES[1]:
        a, b = st.columns(2)
        width_cm = a.number_input("Ancho (cm)", min_value=0.0, value=0.0, key=f"{prefix}_width")
        height_cm = b.number_input("Alto (cm)", min_value=0.0, value=0.0, key=f"{prefix}_height")
        return {"content_type": "area", "content_value": round(width_cm * height_cm, 2), "content_unit": "cm²", "width_cm": width_cm, "height_cm": height_cm}
    if content_type == CONTENT_TYPES[2]:
        weight_g = st.number_input("Peso por unidad (g)", min_value=0.0, value=0.0, key=f"{prefix}_weight")
        return {"content_type": "weight", "content_value": weight_g, "content_unit": "g"}
    if content_type == CONTENT_TYPES[3]:
        volume_ml = st.number_input("Volumen por unidad (ml)", min_value=0.0, value=0.0, key=f"{prefix}_volume")
        return {"content_type": "volume", "content_value": volume_ml, "content_unit": "ml"}
    return {"content_type": "piece", "content_value": 0.0, "content_unit": ""}


def _items() -> list[dict]:
    rows = read_list("inventory_registry")
    normalized = []
    for raw in rows:
        row = dict(raw)
        purchased = _num(row.get("purchased_quantity") or row.get("quantity") or 1, 1)
        total_cost = _num(row.get("purchase_cost") or row.get("total_cost"))
        unit_cost = _num(row.get("unit_cost"), total_cost / max(purchased, 1))
        stock = _num(row.get("available_quantity") if row.get("available_quantity") is not None else row.get("stock"))
        normalized.append({
            **row,
            "item_id": str(row.get("item_id") or row.get("sku") or uuid4().hex[:8].upper()),
            "sku": str(row.get("sku") or row.get("item_id") or ""),
            "name": str(row.get("name") or row.get("product_name") or "Material").strip(),
            "category": str(row.get("category") or "Otro"),
            "unit_name": str(row.get("unit_name") or row.get("unit") or "unidad"),
            "available_quantity": stock,
            "minimum_stock": _num(row.get("minimum_stock") or row.get("reorder_point")),
            "maximum_stock": _num(row.get("maximum_stock")),
            "unit_cost": unit_cost,
            "purchase_cost": total_cost or unit_cost * max(purchased, 1),
            "purchased_quantity": purchased,
            "supplier": str(row.get("supplier") or ""),
            "location": str(row.get("location") or "Almacén principal"),
            "lot": str(row.get("lot") or ""),
            "expiry_date": str(row.get("expiry_date") or ""),
            "active": bool(row.get("active", True)),
            "purchase_currency": str(row.get("purchase_currency") or get_currency()),
            "exchange_rate_used": _num(row.get("exchange_rate_used"), 1.0),
            "payment_method": str(row.get("payment_method") or ""),
            "content_type": str(row.get("content_type") or "piece"),
            "content_value": _num(row.get("content_value")),
            "content_unit": str(row.get("content_unit") or ""),
        })
    return normalized


def _save(rows: list[dict]) -> None:
    save_list("inventory_registry", rows)


def _build_csv(rows: list[dict]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow([row.get(column, "") for column in CSV_COLUMNS])
    return buffer.getvalue().encode("utf-8")


def _movement(item: dict, movement_type: str, quantity: float, reason: str, unit_cost: float = 0.0, purchase_detail: dict | None = None) -> None:
    before = _num(item.get("available_quantity"))
    positive = movement_type in {"Entrada", "Ajuste positivo", "Devolución"}
    after = before + quantity if positive else max(0.0, before - quantity)
    if movement_type == "Entrada" and unit_cost > 0:
        old_value = before * _num(item.get("unit_cost"))
        incoming_value = quantity * unit_cost
        item["unit_cost"] = (old_value + incoming_value) / max(after, 0.00001)
        item["purchase_cost"] = item["unit_cost"] * max(_num(item.get("purchased_quantity")), 1)
        if purchase_detail:
            item["purchase_currency"] = purchase_detail.get("currency", item.get("purchase_currency"))
            item["exchange_rate_used"] = purchase_detail.get("exchange_rate", item.get("exchange_rate_used"))
            item["payment_method"] = purchase_detail.get("payment_method", item.get("payment_method"))
            if purchase_detail.get("supplier"):
                item["supplier"] = purchase_detail["supplier"]
    item["available_quantity"] = after
    movements = read_list("inventory_movements")
    movement_record = {
        "movement_id": f"MOV-{uuid4().hex[:8].upper()}", "created_at_utc": _now(),
        "item_id": item["item_id"], "item_name": item["name"],
        "movement_type": movement_type, "quantity": quantity, "reason": reason.strip(),
        "previous_quantity": before, "resulting_quantity": after,
        "unit_cost": unit_cost or _num(item.get("unit_cost")),
        "total_value": quantity * (unit_cost or _num(item.get("unit_cost"))),
    }
    if purchase_detail:
        movement_record.update({
            "supplier": purchase_detail.get("supplier", ""),
            "purchase_currency": purchase_detail.get("currency", ""),
            "exchange_rate_used": purchase_detail.get("exchange_rate", 1.0),
            "payment_method": purchase_detail.get("payment_method", ""),
            "material_subtotal": purchase_detail.get("material_subtotal", 0.0),
            "shipping_cost": purchase_detail.get("shipping_cost", 0.0),
            "tax_amount": purchase_detail.get("tax_amount", 0.0),
            "invoice_number": purchase_detail.get("invoice_number", ""),
        })
    movements.append(movement_record)
    save_list("inventory_movements", movements)


def _dashboard(rows: list[dict]) -> None:
    active = [r for r in rows if r.get("active", True)]
    low = [r for r in active if _num(r["minimum_stock"]) > 0 and _num(r["available_quantity"]) <= _num(r["minimum_stock"])]
    out = [r for r in active if _num(r["available_quantity"]) <= 0]
    value = sum(_num(r["available_quantity"]) * _num(r["unit_cost"]) for r in active)
    cols = st.columns(5)
    cols[0].metric("Artículos activos", len(active))
    cols[1].metric("Valor del inventario", f"${value:,.2f}")
    cols[2].metric("Stock bajo", len(low))
    cols[3].metric("Agotados", len(out))
    cols[4].metric("Movimientos", len(read_list("inventory_movements")))
    if low:
        st.markdown("#### Reposición prioritaria")
        st.dataframe([
            {"SKU": r["sku"] or r["item_id"], "Artículo": r["name"], "Existencia": r["available_quantity"],
             "Mínimo": r["minimum_stock"], "Sugerido": max(_num(r["maximum_stock"]) - _num(r["available_quantity"]), _num(r["minimum_stock"]) * 2 - _num(r["available_quantity"])),
             "Unidad": r["unit_name"]}
            for r in sorted(low, key=lambda x: _num(x["available_quantity"]) - _num(x["minimum_stock"]))
        ], use_container_width=True, hide_index=True)
    categories: dict[str, float] = {}
    for r in active:
        categories[r["category"]] = categories.get(r["category"], 0) + _num(r["available_quantity"]) * _num(r["unit_cost"])
    if categories:
        st.markdown("#### Valor por categoría")
        st.dataframe([{"Categoría": k, "Valor ($)": round(v, 2)} for k, v in sorted(categories.items(), key=lambda x: x[1], reverse=True)], use_container_width=True, hide_index=True)


def _purchase_invoice(rows: list[dict]) -> None:
    """Registra una factura de compra con varias líneas que comparten un
    mismo envío y un mismo impuesto — el caso real de comprar varios
    materiales en un solo pedido al proveedor. Antes había que registrar
    cada artículo por separado y adivinar cuánto del flete/impuesto le tocaba
    a cada uno; aquí se reparte proporcionalmente al subtotal de cada línea y
    se actualiza el costo real (landed) de cada artículo en un solo paso."""
    st.caption(
        "Para cuando compras varios materiales de una vez y todos comparten el mismo "
        "envío y el mismo impuesto: agrega una línea por artículo, y el sistema reparte "
        "el envío y el impuesto entre ellas según cuánto pesa cada una en la factura."
    )
    active_items = {
        f"{r['name']} · {r['sku'] or r['item_id']} · stock {r['available_quantity']:,.2f} {r['unit_name']}": r
        for r in rows if r.get("active", True)
    }
    if not active_items:
        st.info("Registra artículos en la pestaña 'Registrar' antes de crear una factura de compra.")
        return

    draft_lines: list[dict] = st.session_state.get("purchase_invoice_draft_lines", [])

    base_currency = get_currency()
    currency = st.selectbox(
        "Moneda de la factura", CURRENCIES,
        index=CURRENCIES.index(base_currency) if base_currency in CURRENCIES else 0,
        key="pinv_currency",
    )

    with st.form("purchase_invoice_add_line", clear_on_submit=True):
        line_cols = st.columns([3, 1, 1])
        item_label = line_cols[0].selectbox("Artículo", tuple(active_items), key="pinv_item")
        quantity = line_cols[1].number_input("Cantidad", min_value=0.0, value=0.0, step=1.0, key="pinv_qty")
        unit_price = line_cols[2].number_input(f"Precio unitario ({currency})", min_value=0.0, value=0.0, step=0.1, format="%.4f", key="pinv_price")
        add_line = st.form_submit_button("Agregar línea a la factura", use_container_width=True)
    if add_line:
        if quantity <= 0 or unit_price <= 0:
            st.error("Cantidad y precio unitario deben ser mayores que cero.")
        else:
            item = active_items[item_label]
            draft_lines.append({
                "item_id": item["item_id"], "name": item["name"], "unit_name": item["unit_name"],
                "quantity": float(quantity), "unit_price": float(unit_price),
            })
            st.session_state["purchase_invoice_draft_lines"] = draft_lines
            st.rerun()

    if not draft_lines:
        st.info("Agrega al menos una línea para poder registrar la factura.")
        return

    st.markdown("#### Líneas de esta factura")
    for index, line in enumerate(draft_lines):
        with st.container(border=True):
            item_cols = st.columns([3, 1, 1, 1])
            subtotal = line["quantity"] * line["unit_price"]
            item_cols[0].write(f"**{line['name']}**")
            item_cols[1].write(f"{line['quantity']:,.2f} {line['unit_name']}")
            item_cols[2].write(f"{subtotal:,.2f} {currency}")
            if item_cols[3].button("Quitar", key=f"pinv_remove_{index}"):
                draft_lines.pop(index)
                st.session_state["purchase_invoice_draft_lines"] = draft_lines
                st.rerun()

    lines_subtotal = sum(line["quantity"] * line["unit_price"] for line in draft_lines)
    st.metric("Subtotal de artículos (sin envío ni impuestos)", f"{lines_subtotal:,.2f} {currency}")

    st.markdown("##### Datos compartidos de la factura")
    same_currency = currency == base_currency
    with st.form("purchase_invoice_header"):
        header_cols = st.columns(3)
        supplier = header_cols[0].text_input("Proveedor")
        invoice_number = header_cols[1].text_input("N° de factura / control")
        payment_method = header_cols[2].selectbox("Método de pago", PAYMENT_METHODS)
        rate_cols = st.columns(2)
        exchange_rate = rate_cols[0].number_input(
            f"Tasa de cambio usada (1 {base_currency} = ? {currency})",
            min_value=0.0001, value=1.0 if same_currency else _default_exchange_rate(currency, base_currency),
            step=0.01, format="%.4f", disabled=same_currency,
        )
        invoice_date = rate_cols[1].date_input("Fecha de la factura", value=date.today())
        shared_cols = st.columns(2)
        shipping_cost = shared_cols[0].number_input(f"Envío / flete TOTAL de la factura ({currency})", min_value=0.0, value=0.0, step=1.0)
        tax_amount = shared_cols[1].number_input(f"Impuestos TOTALES de la factura ({currency})", min_value=0.0, value=0.0, step=1.0)
        submit_invoice = st.form_submit_button("Registrar factura completa", type="primary", use_container_width=True)

    if submit_invoice:
        effective_rate = 1.0 if same_currency else float(exchange_rate)
        subtotals = [line["quantity"] * line["unit_price"] for line in draft_lines]
        allocations = allocate_shared_costs(subtotals, float(shipping_cost), float(tax_amount))
        by_id = {row["item_id"]: row for row in rows}
        updated_lines = 0
        for line, subtotal, (allocated_shipping, allocated_tax) in zip(draft_lines, subtotals, allocations):
            item = by_id.get(line["item_id"])
            if item is None:
                continue
            unit_cost, _total = _landed_unit_cost(subtotal, allocated_shipping, allocated_tax, effective_rate, line["quantity"])
            purchase_detail = {
                "currency": currency, "exchange_rate": effective_rate, "payment_method": payment_method,
                "supplier": supplier.strip(), "material_subtotal": subtotal,
                "shipping_cost": allocated_shipping, "tax_amount": allocated_tax,
                "invoice_number": invoice_number.strip(),
            }
            reason = f"Factura {invoice_number.strip()}" if invoice_number.strip() else f"Factura de compra {invoice_date.isoformat()}"
            _movement(item, "Entrada", line["quantity"], reason, unit_cost, purchase_detail=purchase_detail)
            updated_lines += 1
        _save(rows)
        st.session_state["purchase_invoice_draft_lines"] = []
        st.success(
            f"Factura registrada: {updated_lines} artículo(s) actualizados, con el envío y los impuestos "
            "repartidos proporcionalmente entre las líneas — no hace falta adivinar cuánto le tocaba a cada uno."
        )
        st.rerun()


def _register(rows: list[dict]) -> None:
    with st.form("enterprise_inventory_item", clear_on_submit=True):
        a, b, c, d = st.columns(4)
        sku = a.text_input("SKU / código")
        name = b.text_input("Nombre obligatorio")
        category = c.selectbox("Categoría", CATEGORIES)
        unit = d.selectbox("Unidad", UNITS)
        a, b, c = st.columns(3)
        quantity = a.number_input("Cantidad comprada / existencia inicial", min_value=0.0, value=0.0)
        minimum = b.number_input("Stock mínimo", min_value=0.0, value=0.0)
        maximum = c.number_input("Stock máximo", min_value=0.0, value=0.0)

        st.markdown("##### ¿Qué costó realmente traer este material?")
        purchase = _purchase_inputs("reg")

        st.markdown("##### Contenido físico (para calcular merma después)")
        content = _content_inputs("reg")

        a, b, c = st.columns(3)
        location = a.text_input("Ubicación", value="Almacén principal")
        lot = b.text_input("Lote")
        expiry = c.date_input("Vencimiento", value=None)
        submit = st.form_submit_button("Registrar artículo", type="primary", use_container_width=True)
    if submit:
        if not name.strip():
            st.error("El nombre es obligatorio.")
            return
        if purchase["material_subtotal"] <= 0:
            st.error("El costo del material debe ser mayor que cero.")
            return
        item_id = sku.strip() or uuid4().hex[:8].upper()
        if any(str(r.get("item_id")) == item_id or (sku.strip() and str(r.get("sku")) == sku.strip()) for r in rows):
            st.error("El SKU o ID ya existe.")
            return

        unit_cost, landed_total = _landed_unit_cost(
            purchase["material_subtotal"], purchase["shipping_cost"], purchase["tax_amount"],
            purchase["exchange_rate"], max(quantity, 1),
        )
        item = {
            "item_id": item_id, "sku": sku.strip(), "name": name.strip(), "category": category,
            "unit_name": unit, "available_quantity": 0.0, "minimum_stock": float(minimum),
            "maximum_stock": float(maximum), "unit_cost": unit_cost,
            "purchase_cost": landed_total, "purchased_quantity": float(max(quantity, 1)),
            "supplier": purchase["supplier"], "location": location.strip(), "lot": lot.strip(),
            "expiry_date": expiry.isoformat() if expiry else "", "active": True, "created_at_utc": _now(),
            "purchase_currency": purchase["currency"], "exchange_rate_used": purchase["exchange_rate"],
            "payment_method": purchase["payment_method"],
            "content_type": content["content_type"], "content_value": content["content_value"], "content_unit": content["content_unit"],
        }
        rows.append(item)
        # La existencia inicial se registra siempre como un movimiento de "Entrada", nunca
        # asignada directamente al campo `available_quantity` del ítem: así el historial de
        # movimientos siempre explica de dónde salió cada unidad de existencia, y evita
        # contarla dos veces (antes: se fijaba aquí Y se volvía a sumar en `_movement`).
        _save(rows)
        if quantity > 0:
            _movement(item, "Entrada", float(quantity), "Existencia inicial", unit_cost, purchase_detail=purchase)
            _save(rows)
        st.success(f"Artículo registrado. Costo unitario real (con envío e impuestos incluidos): {format_money(unit_cost)}.")
        st.rerun()


def _catalog(rows: list[dict]) -> None:
    a, b, c = st.columns([2, 1, 1])
    query = a.text_input("Buscar por nombre, SKU o lote")
    category = b.selectbox("Filtrar categoría", ("Todas", *CATEGORIES))
    status = c.selectbox("Estado", ("Todos", "Disponible", "Stock bajo", "Agotado", "Inactivo"))
    filtered = []
    for r in rows:
        haystack = f"{r['name']} {r['sku']} {r['item_id']} {r['lot']}".casefold()
        if query and query.casefold() not in haystack:
            continue
        if category != "Todas" and r["category"] != category:
            continue
        stock = _num(r["available_quantity"])
        low = _num(r["minimum_stock"]) > 0 and stock <= _num(r["minimum_stock"])
        current = "Inactivo" if not r.get("active", True) else "Agotado" if stock <= 0 else "Stock bajo" if low else "Disponible"
        if status != "Todos" and current != status:
            continue
        filtered.append((r, current))
    st.dataframe([
        {"SKU": r["sku"] or r["item_id"], "Artículo": r["name"], "Categoría": r["category"],
         "Existencia": r["available_quantity"], "Unidad": r["unit_name"], "Costo unitario": round(_num(r["unit_cost"]), 4),
         "Valor": round(_num(r["available_quantity"]) * _num(r["unit_cost"]), 2), "Proveedor": r["supplier"],
         "Método de pago": r.get("payment_method", ""), "Moneda de compra": r.get("purchase_currency", ""),
         "Contenido/unidad": f"{r['content_value']:,.2f} {r['content_unit']}".strip() if r.get("content_unit") else "—",
         "Ubicación": r["location"], "Estado": state}
        for r, state in filtered
    ], use_container_width=True, hide_index=True)
    if filtered:
        st.download_button(
            "Descargar catálogo filtrado (CSV)",
            data=_build_csv([r for r, _state in filtered]),
            file_name=f"inventario_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def _movements(rows: list[dict]) -> None:
    if not rows:
        st.info("Registra artículos antes de crear movimientos.")
        return
    labels = {f"{r['name']} · {r['sku'] or r['item_id']} · stock {r['available_quantity']:,.2f}": r for r in rows if r.get("active", True)}
    selected = st.selectbox("Artículo", tuple(labels), key="mov_item_select")
    movement_type = st.selectbox("Movimiento", MOVEMENTS, key="mov_type_select")
    is_entrada = movement_type == "Entrada"
    with st.form("enterprise_inventory_movement", clear_on_submit=True):
        purchase = None
        if is_entrada:
            st.caption("Es una nueva compra: registra exactamente lo que costó traerla, para que el costo unitario quede real.")
            purchase = _purchase_inputs("mov", default_supplier=labels[selected].get("supplier", ""))
            quantity = st.number_input("Cantidad comprada", min_value=0.0001, value=1.0, key="mov_qty_entrada")
        else:
            quantity = st.number_input("Cantidad", min_value=0.0001, value=1.0, key="mov_qty_otro")
        reason = st.text_input("Motivo / documento / trabajo")
        submit = st.form_submit_button("Registrar movimiento", type="primary", use_container_width=True)
    if submit:
        item = labels[selected]
        negative = movement_type in {"Salida", "Ajuste negativo", "Merma"}
        if negative and quantity > _num(item["available_quantity"]):
            st.error("La salida supera la existencia disponible.")
            return
        if is_entrada:
            if purchase["material_subtotal"] <= 0:
                st.error("El costo del material debe ser mayor que cero para registrar la entrada.")
                return
            unit_cost, _landed_total = _landed_unit_cost(
                purchase["material_subtotal"], purchase["shipping_cost"], purchase["tax_amount"],
                purchase["exchange_rate"], quantity,
            )
            _movement(item, movement_type, float(quantity), reason or "Compra", unit_cost, purchase_detail=purchase)
            st.success(f"Entrada registrada. Costo unitario real de esta compra: {format_money(unit_cost)}.")
        else:
            _movement(item, movement_type, float(quantity), reason or "Movimiento manual")
            st.success("Movimiento registrado con trazabilidad.")
        _save(rows)
        st.rerun()
    history = list(reversed(read_list("inventory_movements")[-200:]))
    if history:
        st.markdown("#### Historial reciente")
        st.dataframe(history, use_container_width=True, hide_index=True)


def _counts(rows: list[dict]) -> None:
    st.caption("Registra un conteo físico; el sistema genera el ajuste y conserva la diferencia.")
    if not rows:
        return
    labels = {f"{r['name']} · sistema {r['available_quantity']:,.2f} {r['unit_name']}": r for r in rows if r.get("active", True)}
    with st.form("inventory_physical_count"):
        selected = st.selectbox("Artículo contado", tuple(labels))
        physical = st.number_input("Cantidad física", min_value=0.0, value=0.0)
        note = st.text_input("Responsable / observación")
        submit = st.form_submit_button("Aplicar conteo físico", type="primary", use_container_width=True)
    if submit:
        item = labels[selected]
        system = _num(item["available_quantity"])
        difference = physical - system
        if math.isclose(difference, 0.0, abs_tol=0.0001):
            st.info("No existe diferencia.")
            return
        movement = "Ajuste positivo" if difference > 0 else "Ajuste negativo"
        _movement(item, movement, abs(difference), f"Conteo físico: {note}".strip())
        _save(rows)
        st.success(f"Conteo aplicado. Diferencia: {difference:+,.2f} {item['unit_name']}.")
        st.rerun()


def _replenishment(rows: list[dict]) -> None:
    candidates = []
    for r in rows:
        stock, minimum, maximum = _num(r["available_quantity"]), _num(r["minimum_stock"]), _num(r["maximum_stock"])
        if minimum > 0 and stock <= minimum:
            target = maximum if maximum > minimum else minimum * 2
            qty = max(target - stock, 0)
            candidates.append({"SKU": r["sku"] or r["item_id"], "Artículo": r["name"], "Proveedor": r["supplier"],
                               "Existencia": stock, "Mínimo": minimum, "Comprar": round(qty, 2), "Unidad": r["unit_name"],
                               "Costo estimado": round(qty * _num(r["unit_cost"]), 2)})
    if not candidates:
        st.success("No hay artículos que requieran reposición.")
    else:
        st.dataframe(candidates, use_container_width=True, hide_index=True)
        st.metric("Compra estimada", f"${sum(r['Costo estimado'] for r in candidates):,.2f}")
        render_info_card("Siguiente paso", "Convierte esta sugerencia en una solicitud o compra desde Compras y Proveedores.", "ABASTECIMIENTO")


def _reserved_for(item_id: str, reservations: list[dict]) -> float:
    return sum(
        _num(row.get("quantity"))
        for row in reservations
        if str(row.get("item_id")) == str(item_id) and row.get("status") == "Activa"
    )


def _reservations(rows: list[dict]) -> None:
    st.caption("Aparta existencia para un pedido, cotización o trabajo de producción sin descontarla todavía del inventario.")
    reservations = read_list("inventory_reservations")
    active_rows = [r for r in rows if r.get("active", True)]
    if not active_rows:
        st.info("Registra artículos antes de reservar.")
    else:
        labels = {f"{r['name']} · disponible {max(_num(r['available_quantity']) - _reserved_for(r['item_id'], reservations), 0.0):,.2f} {r['unit_name']}": r for r in active_rows}
        with st.form("inventory_reservation_form", clear_on_submit=True):
            selected = st.selectbox("Artículo", tuple(labels))
            item = labels[selected]
            free = max(_num(item["available_quantity"]) - _reserved_for(item["item_id"], reservations), 0.0)
            a, b, c, d = st.columns(4)
            quantity = a.number_input("Cantidad a reservar", min_value=0.0, max_value=float(free) if free > 0 else 0.0, value=0.0, step=1.0)
            source = b.selectbox("Origen", ("Pedido", "Producción", "Cotización", "Uso interno", "Otro"))
            reference = c.text_input("Referencia")
            due_date = d.date_input("Vence", value=date.today())
            responsible = st.text_input("Responsable")
            submit = st.form_submit_button("Reservar", type="primary", use_container_width=True)
        if submit:
            if quantity <= 0:
                st.error("La cantidad a reservar debe ser mayor que cero.")
            elif quantity > free:
                st.error("La cantidad a reservar supera la existencia disponible (ya descontando otras reservas activas).")
            else:
                reservations.append({
                    "reservation_id": f"RSV-{uuid4().hex[:8].upper()}",
                    "item_id": item["item_id"], "quantity": float(quantity), "source": source,
                    "reference": reference.strip(), "due_date": due_date.isoformat(),
                    "responsible": responsible.strip() or "Sin asignar", "note": "",
                    "status": "Activa", "created_at_utc": _now(),
                })
                save_list("inventory_reservations", reservations)
                st.success("Reserva creada. La existencia disponible ya la descuenta en el resto del ERP.")
                st.rerun()

    active_reservations = [row for row in reservations if row.get("status") == "Activa"]
    if not active_reservations:
        st.info("No hay reservas activas.")
        return
    st.markdown("#### Reservas activas")
    names = {r["item_id"]: r["name"] for r in rows}
    for reservation in reversed(active_reservations[-50:]):
        with st.container(border=True):
            cols = st.columns([3, 1, 1])
            cols[0].markdown(f"**{names.get(reservation.get('item_id'), 'Material no disponible')}**")
            cols[0].caption(f"{reservation.get('source', '')} · {reservation.get('reference', '')} · vence {reservation.get('due_date', '')} · {reservation.get('responsible', '')}")
            cols[1].metric("Cantidad", f"{_num(reservation.get('quantity')):,.2f}")
            if cols[2].button("Liberar", key=f"release_{reservation.get('reservation_id')}", use_container_width=True):
                updated = []
                for row in reservations:
                    current = dict(row)
                    if current.get("reservation_id") == reservation.get("reservation_id"):
                        current["status"] = "Liberada"
                        current["released_at_utc"] = _now()
                    updated.append(current)
                save_list("inventory_reservations", updated)
                st.rerun()


def render_inventory_enterprise() -> None:
    render_page_header("Inventario empresarial", "Controla existencias, costos, movimientos, conteos, lotes y reposición desde una sola área.")
    rows = _items()
    tabs = st.tabs(("Panel", "Registrar", "Factura de compra", "Catálogo", "Movimientos", "Reservas", "Conteo físico", "Reposición"))
    with tabs[0]: _dashboard(rows)
    with tabs[1]: _register(rows)
    with tabs[2]: _purchase_invoice(rows)
    with tabs[3]: _catalog(rows)
    with tabs[4]: _movements(rows)
    with tabs[5]: _reservations(rows)
    with tabs[6]: _counts(rows)
    with tabs[7]: _replenishment(rows)
    st.caption("Los papeles, blancos de sublimación, materiales de Cameo y plastificación registrados aquí son reutilizados automáticamente por Producción y Costeo.")
