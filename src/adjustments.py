"""Anulaciones y reversos operativos para CopyMary ERP."""

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cash_amount(reference: str, cash: list[dict], movement_type: str) -> float:
    return sum(
        float(item.get("amount", 0.0))
        for item in cash
        if item.get("movement_type") == movement_type
        and str(item.get("reference", "")) == reference
    )


def _reverse_inventory(purchase: dict, inventory: list[dict]) -> tuple[list[dict], bool]:
    item_id = str(purchase.get("inventory_item_id", ""))
    quantity = float(purchase.get("quantity", 0.0))
    total = float(purchase.get("total", 0.0))
    result: list[dict] = []
    matched = False
    for item in inventory:
        current = dict(item)
        if item_id and str(item.get("item_id", "")) == item_id:
            if float(item.get("available_quantity", 0.0)) < quantity:
                return inventory, False
            current["available_quantity"] = float(item.get("available_quantity", 0.0)) - quantity
            current["purchased_quantity"] = max(float(item.get("purchased_quantity", 0.0)) - quantity, 0.0)
            current["purchase_cost"] = max(float(item.get("purchase_cost", 0.0)) - total, 0.0)
            matched = True
        result.append(current)
    return result, matched


def render_adjustments() -> None:
    with st.container(border=True):
        render_page_header("Anulaciones y ajustes", "Revierte ventas y compras sin descuadrar Caja ni Inventario.")
        st.caption("Cada anulación queda registrada y solo puede aplicarse una vez.")

    sales = _rows("sales_registry")
    purchases = _rows("purchases_registry")
    cash = _rows("cash_movements")
    inventory = _rows("inventory_registry")
    adjustments = _rows("adjustment_records")

    reversed_sales = {str(item.get("reference_id", "")) for item in adjustments if item.get("kind") == "Venta"}
    reversed_purchases = {str(item.get("reference_id", "")) for item in adjustments if item.get("kind") == "Compra"}

    metrics = st.columns(3)
    metrics[0].metric("Ajustes", str(len(adjustments)))
    metrics[1].metric("Ventas anuladas", str(len(reversed_sales)))
    metrics[2].metric("Compras anuladas", str(len(reversed_purchases)))

    sale_tab, purchase_tab, history_tab = st.tabs(("Anular venta", "Anular compra", "Historial"))

    with sale_tab:
        available = [sale for sale in sales if str(sale.get("sale_id", "")) not in reversed_sales and sale.get("order_status") != "Cancelado"]
        if not available:
            st.info("No hay ventas disponibles para anular.")
        else:
            options = {f"{sale.get('description', 'Venta')} · {format_money(float(sale.get('total', 0.0)))}": sale for sale in available}
            with st.form("cancel_sale_form"):
                selected = options[st.selectbox("Venta", tuple(options.keys()))]
                reason = st.text_area("Motivo", max_chars=300)
                confirm = st.checkbox("Confirmo la anulación y el reverso de Caja.")
                submitted = st.form_submit_button("Anular venta", type="primary", use_container_width=True, disabled=not confirm)
            if submitted:
                sale_id = str(selected.get("sale_id", ""))
                refunded = _cash_amount(sale_id, cash, "Ingreso")
                if refunded > 0:
                    cash.append({"movement_id": uuid4().hex[:10], "created_at_utc": _now(), "movement_type": "Egreso", "category": "Reembolso de venta", "amount": refunded, "payment_method": selected.get("payment_method", "Otro"), "reference": f"REV-{sale_id}", "notes": reason.strip()})
                updated_sales = []
                for sale in sales:
                    current = dict(sale)
                    if str(sale.get("sale_id", "")) == sale_id:
                        current["order_status"] = "Cancelado"
                        current["payment_status"] = "Reembolsado" if refunded > 0 else "Cancelado"
                        current["cash_registered"] = False
                    updated_sales.append(current)
                adjustments.append({"adjustment_id": uuid4().hex[:10], "created_at_utc": _now(), "kind": "Venta", "reference_id": sale_id, "description": selected.get("description", "Venta"), "amount": refunded, "reason": reason.strip(), "inventory_reversed": False})
                st.session_state["sales_registry"] = updated_sales
                st.session_state["cash_movements"] = cash
                st.session_state["adjustment_records"] = adjustments
                st.rerun()

    with purchase_tab:
        available = [purchase for purchase in purchases if str(purchase.get("purchase_id", "")) not in reversed_purchases and purchase.get("receipt_status") != "Cancelada"]
        if not available:
            st.info("No hay compras disponibles para anular.")
        else:
            options = {f"{purchase.get('material_name', 'Compra')} · {format_money(float(purchase.get('total', 0.0)))}": purchase for purchase in available}
            with st.form("cancel_purchase_form"):
                selected = options[st.selectbox("Compra", tuple(options.keys()))]
                reason = st.text_area("Motivo", max_chars=300)
                confirm = st.checkbox("Confirmo la anulación y sus reversos.")
                submitted = st.form_submit_button("Anular compra", type="primary", use_container_width=True, disabled=not confirm)
            if submitted:
                purchase_id = str(selected.get("purchase_id", ""))
                updated_inventory = inventory
                inventory_reversed = False
                if selected.get("inventory_applied"):
                    updated_inventory, inventory_reversed = _reverse_inventory(selected, inventory)
                    if not inventory_reversed:
                        st.error("No se puede anular porque parte del material ya fue consumido.")
                        st.stop()
                refunded = _cash_amount(purchase_id, cash, "Egreso")
                if refunded > 0:
                    cash.append({"movement_id": uuid4().hex[:10], "created_at_utc": _now(), "movement_type": "Ingreso", "category": "Reembolso de compra", "amount": refunded, "payment_method": selected.get("payment_method", "Otro"), "reference": f"REV-{purchase_id}", "notes": reason.strip()})
                updated_purchases = []
                for purchase in purchases:
                    current = dict(purchase)
                    if str(purchase.get("purchase_id", "")) == purchase_id:
                        current["receipt_status"] = "Cancelada"
                        current["payment_status"] = "Reembolsado" if refunded > 0 else "Cancelado"
                        current["inventory_applied"] = False
                        current["cash_registered"] = False
                    updated_purchases.append(current)
                adjustments.append({"adjustment_id": uuid4().hex[:10], "created_at_utc": _now(), "kind": "Compra", "reference_id": purchase_id, "description": selected.get("material_name", "Compra"), "amount": refunded, "reason": reason.strip(), "inventory_reversed": inventory_reversed})
                st.session_state["purchases_registry"] = updated_purchases
                st.session_state["inventory_registry"] = updated_inventory
                st.session_state["cash_movements"] = cash
                st.session_state["adjustment_records"] = adjustments
                st.rerun()

    with history_tab:
        if not adjustments:
            st.info("Todavía no hay ajustes registrados.")
        for item in reversed(adjustments):
            with st.container(border=True):
                row = st.columns([3, 1])
                row[0].markdown(f"### Anulación de {item.get('kind', '')}")
                row[0].caption(f"{item.get('description', '')} · Ref. {item.get('reference_id', '')}")
                row[1].metric("Revertido", format_money(float(item.get("amount", 0.0))))
                st.write(f"Motivo: {item.get('reason') or 'No indicado'}")

    render_info_card("Trazabilidad", "Los movimientos originales no se eliminan; se crean movimientos opuestos para conservar el historial.", "CONTROL DE AJUSTES")
