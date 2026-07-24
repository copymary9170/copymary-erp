"""Recepción de mercancía.

Solo una recepción aceptada aumenta inventario. El costo promedio ponderado se
calcula aquí y cada receipt_id se procesa una sola vez.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.catalog_items import find_by_id, get_catalog_items
from src.purchase_states import validate_reception
from src.session_utils import read_list, save_list

RECEIPTS_KEY = "goods_receipts"
INVENTORY_KEY = "inventory_registry"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def weighted_average_cost(current_qty: float, current_cost: float, accepted_qty: float, received_cost: float) -> float:
    total_qty = float(current_qty) + float(accepted_qty)
    if total_qty <= 0:
        return 0.0
    return round(((float(current_qty) * float(current_cost)) + (float(accepted_qty) * float(received_cost))) / total_qty, 6)


def receipt_already_processed(receipt_id: str) -> bool:
    return any(str(row.get("receipt_id")) == str(receipt_id) and row.get("status") == "Aceptada" for row in read_list(RECEIPTS_KEY))


def _find_inventory_index(inventory: list[dict], catalog_item_id: str) -> int | None:
    for index, row in enumerate(inventory):
        if str(row.get("catalog_item_id") or "") == str(catalog_item_id):
            return index
    return None


def accept_receipt(*, receipt_id: str, catalog_item_id: str, accepted_qty: float, unit_cost: float, ordered_qty: float | None = None, already_received: float = 0.0, supplier_id: str = "", purchase_id: str = "", lot: str = "", expiry: str = "", notes: str = "") -> dict:
    if receipt_already_processed(receipt_id):
        return {"ok": True, "idempotent": True, "message": "La recepción ya había sido procesada."}
    item = find_by_id(catalog_item_id)
    if item is None:
        return {"ok": False, "errors": ["El artículo no existe en el Catálogo."]}
    errors = []
    if accepted_qty <= 0:
        errors.append("La cantidad aceptada debe ser mayor que cero.")
    if unit_cost < 0:
        errors.append("El costo unitario no puede ser negativo.")
    if ordered_qty is not None:
        errors.extend(validate_reception(ordered=ordered_qty, already_received=already_received, receiving_now=accepted_qty))
    if errors:
        return {"ok": False, "errors": errors}

    inventory = read_list(INVENTORY_KEY)
    index = _find_inventory_index(inventory, catalog_item_id)
    if index is None:
        inventory.append({
            "id": uuid4().hex[:8].upper(), "catalog_item_id": item.item_id,
            "sku": item.sku, "name": item.name, "material_name": item.name,
            "unit_name": item.inventory_unit, "quantity": float(accepted_qty),
            "stock": float(accepted_qty), "average_cost": float(unit_cost),
            "unit_cost": float(unit_cost), "last_receipt_id": receipt_id,
            "updated_at_utc": _now(),
        })
    else:
        row = dict(inventory[index])
        current_qty = float(row.get("quantity", row.get("stock", 0.0)) or 0.0)
        current_cost = float(row.get("average_cost", row.get("unit_cost", 0.0)) or 0.0)
        new_qty = current_qty + float(accepted_qty)
        new_cost = weighted_average_cost(current_qty, current_cost, accepted_qty, unit_cost)
        row.update({"quantity": new_qty, "stock": new_qty, "average_cost": new_cost, "unit_cost": new_cost, "last_receipt_id": receipt_id, "updated_at_utc": _now()})
        inventory[index] = row
    save_list(INVENTORY_KEY, inventory)

    receipts = read_list(RECEIPTS_KEY)
    receipts.append({
        "receipt_id": receipt_id, "purchase_id": purchase_id,
        "catalog_item_id": item.item_id, "catalog_sku": item.sku,
        "item_name": item.name, "supplier_id": supplier_id,
        "accepted_qty": float(accepted_qty), "unit_cost": float(unit_cost),
        "lot": lot, "expiry": expiry, "notes": notes,
        "status": "Aceptada", "accepted_at_utc": _now(),
    })
    save_list(RECEIPTS_KEY, receipts)
    return {"ok": True, "idempotent": False, "receipt_id": receipt_id}


def render_goods_receipt() -> None:
    st.title("Recepción de mercancía")
    st.caption("Confirma lo que realmente llegó. Solo la cantidad aceptada aumenta el inventario y actualiza el costo promedio ponderado.")
    items = get_catalog_items(include_inactive=False)
    if not items:
        st.warning("Primero debes crear o migrar artículos en el Catálogo.")
        return
    labels = {f"{item.name} · {item.sku or item.item_id}": item.item_id for item in items}
    with st.form("goods_receipt_form"):
        selected = st.selectbox("Artículo del Catálogo", tuple(labels))
        c1, c2, c3 = st.columns(3)
        accepted_qty = c1.number_input("Cantidad aceptada", min_value=0.0, step=1.0)
        unit_cost = c2.number_input("Costo unitario", min_value=0.0, step=0.01)
        receipt_id = c3.text_input("ID de recepción", value=f"REC-{uuid4().hex[:8].upper()}")
        c4, c5 = st.columns(2)
        supplier_id = c4.text_input("Proveedor / ID")
        purchase_id = c5.text_input("Compra / orden")
        c6, c7 = st.columns(2)
        lot = c6.text_input("Lote")
        expiry = c7.text_input("Vencimiento")
        notes = st.text_area("Observaciones")
        submitted = st.form_submit_button("Aceptar e ingresar al inventario", type="primary")
    if submitted:
        result = accept_receipt(receipt_id=receipt_id.strip(), catalog_item_id=labels[selected], accepted_qty=accepted_qty, unit_cost=unit_cost, supplier_id=supplier_id.strip(), purchase_id=purchase_id.strip(), lot=lot.strip(), expiry=expiry.strip(), notes=notes.strip())
        if result.get("ok"):
            st.success(result.get("message") or "Recepción aceptada e inventario actualizado.")
        else:
            for error in result.get("errors", ["No se pudo procesar la recepción."]):
                st.error(error)

    history = read_list(RECEIPTS_KEY)
    if history:
        st.subheader("Historial de recepciones")
        st.dataframe(history, use_container_width=True, hide_index=True)
