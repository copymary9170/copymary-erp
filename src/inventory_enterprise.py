"""Inventario empresarial para CopyMary ERP.

Mantiene compatibilidad con ``inventory_registry`` y ``inventory_movements``.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4
import math
import streamlit as st

from src.components import render_info_card, render_page_header
from src.session_utils import read_list, save_list

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
        })
    return normalized


def _save(rows: list[dict]) -> None:
    save_list("inventory_registry", rows)


def _movement(item: dict, movement_type: str, quantity: float, reason: str, unit_cost: float = 0.0) -> None:
    before = _num(item.get("available_quantity"))
    positive = movement_type in {"Entrada", "Ajuste positivo", "Devolución"}
    after = before + quantity if positive else max(0.0, before - quantity)
    if movement_type == "Entrada" and unit_cost > 0:
        old_value = before * _num(item.get("unit_cost"))
        incoming_value = quantity * unit_cost
        item["unit_cost"] = (old_value + incoming_value) / max(after, 0.00001)
        item["purchase_cost"] = item["unit_cost"] * max(_num(item.get("purchased_quantity")), 1)
    item["available_quantity"] = after
    movements = read_list("inventory_movements")
    movements.append({
        "movement_id": f"MOV-{uuid4().hex[:8].upper()}", "created_at_utc": _now(),
        "item_id": item["item_id"], "item_name": item["name"],
        "movement_type": movement_type, "quantity": quantity, "reason": reason.strip(),
        "previous_quantity": before, "resulting_quantity": after,
        "unit_cost": unit_cost or _num(item.get("unit_cost")),
        "total_value": quantity * (unit_cost or _num(item.get("unit_cost"))),
    })
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


def _register(rows: list[dict]) -> None:
    with st.form("enterprise_inventory_item", clear_on_submit=True):
        a, b, c, d = st.columns(4)
        sku = a.text_input("SKU / código")
        name = b.text_input("Nombre obligatorio")
        category = c.selectbox("Categoría", CATEGORIES)
        unit = d.selectbox("Unidad", UNITS)
        a, b, c, d = st.columns(4)
        quantity = a.number_input("Existencia inicial", min_value=0.0, value=0.0)
        unit_cost = b.number_input("Costo unitario", min_value=0.0, value=0.0, format="%.4f")
        minimum = c.number_input("Stock mínimo", min_value=0.0, value=0.0)
        maximum = d.number_input("Stock máximo", min_value=0.0, value=0.0)
        a, b, c, d = st.columns(4)
        supplier = a.text_input("Proveedor")
        location = b.text_input("Ubicación", value="Almacén principal")
        lot = c.text_input("Lote")
        expiry = d.date_input("Vencimiento", value=None)
        submit = st.form_submit_button("Registrar artículo", type="primary", use_container_width=True)
    if submit:
        if not name.strip():
            st.error("El nombre es obligatorio.")
            return
        if unit_cost <= 0:
            st.error("El costo unitario debe ser mayor que cero.")
            return
        item_id = sku.strip() or uuid4().hex[:8].upper()
        if any(str(r.get("item_id")) == item_id or (sku.strip() and str(r.get("sku")) == sku.strip()) for r in rows):
            st.error("El SKU o ID ya existe.")
            return
        item = {
            "item_id": item_id, "sku": sku.strip(), "name": name.strip(), "category": category,
            "unit_name": unit, "available_quantity": float(quantity), "minimum_stock": float(minimum),
            "maximum_stock": float(maximum), "unit_cost": float(unit_cost),
            "purchase_cost": float(unit_cost * max(quantity, 1)), "purchased_quantity": float(max(quantity, 1)),
            "supplier": supplier.strip(), "location": location.strip(), "lot": lot.strip(),
            "expiry_date": expiry.isoformat() if expiry else "", "active": True, "created_at_utc": _now(),
        }
        rows.append(item)
        _save(rows)
        if quantity > 0:
            _movement(item, "Entrada", float(quantity), "Existencia inicial", float(unit_cost))
            _save(rows)
        st.success("Artículo registrado e integrado con Producción y Costeo.")
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
         "Valor": round(_num(r["available_quantity"]) * _num(r["unit_cost"]), 2), "Ubicación": r["location"], "Estado": state}
        for r, state in filtered
    ], use_container_width=True, hide_index=True)


def _movements(rows: list[dict]) -> None:
    if not rows:
        st.info("Registra artículos antes de crear movimientos.")
        return
    labels = {f"{r['name']} · {r['sku'] or r['item_id']} · stock {r['available_quantity']:,.2f}": r for r in rows if r.get("active", True)}
    with st.form("enterprise_inventory_movement", clear_on_submit=True):
        selected = st.selectbox("Artículo", tuple(labels))
        a, b, c = st.columns(3)
        movement_type = a.selectbox("Movimiento", MOVEMENTS)
        quantity = b.number_input("Cantidad", min_value=0.0001, value=1.0)
        unit_cost = c.number_input("Costo unitario de entrada", min_value=0.0, value=0.0, format="%.4f")
        reason = st.text_input("Motivo / documento / trabajo")
        submit = st.form_submit_button("Registrar movimiento", type="primary", use_container_width=True)
    if submit:
        item = labels[selected]
        negative = movement_type in {"Salida", "Ajuste negativo", "Merma"}
        if negative and quantity > _num(item["available_quantity"]):
            st.error("La salida supera la existencia disponible.")
            return
        if movement_type == "Entrada" and unit_cost <= 0:
            st.error("Las entradas requieren costo unitario para actualizar el promedio ponderado.")
            return
        _movement(item, movement_type, float(quantity), reason or "Movimiento manual", float(unit_cost))
        _save(rows)
        st.success("Movimiento registrado con trazabilidad.")
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


def render_inventory_enterprise() -> None:
    render_page_header("Inventario empresarial", "Controla existencias, costos, movimientos, conteos, lotes y reposición desde una sola área.")
    rows = _items()
    tabs = st.tabs(("Panel", "Registrar", "Catálogo", "Movimientos", "Conteo físico", "Reposición"))
    with tabs[0]: _dashboard(rows)
    with tabs[1]: _register(rows)
    with tabs[2]: _catalog(rows)
    with tabs[3]: _movements(rows)
    with tabs[4]: _counts(rows)
    with tabs[5]: _replenishment(rows)
    st.caption("Los papeles, blancos de sublimación, materiales de Cameo y plastificación registrados aquí son reutilizados automáticamente por Producción y Costeo.")
