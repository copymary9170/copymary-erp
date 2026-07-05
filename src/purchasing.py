"""Proveedores y compras temporales conectados a Inventario y Caja."""

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _get_list(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save_list(key: str, items: list[dict]) -> None:
    st.session_state[key] = items


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _supplier_name(supplier_id: str, suppliers: list[dict]) -> str:
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")) == supplier_id:
            return str(supplier.get("name", "Proveedor"))
    return "Proveedor no disponible"


def _apply_purchase_to_inventory(purchase: dict, inventory: list[dict]) -> list[dict]:
    item_id = str(purchase.get("inventory_item_id", ""))
    quantity = float(purchase.get("quantity", 0.0))
    total_cost = float(purchase.get("total", 0.0))
    updated_inventory: list[dict] = []
    matched = False

    for item in inventory:
        updated = dict(item)
        if item_id and str(item.get("item_id", "")) == item_id:
            matched = True
            updated["purchase_cost"] = float(item.get("purchase_cost", 0.0)) + total_cost
            updated["purchased_quantity"] = float(item.get("purchased_quantity", 0.0)) + quantity
            updated["available_quantity"] = float(item.get("available_quantity", 0.0)) + quantity
        updated_inventory.append(updated)

    if not matched:
        updated_inventory.append(
            {
                "item_id": item_id or uuid4().hex[:8],
                "name": str(purchase.get("material_name", "Material comprado")),
                "category": str(purchase.get("category", "Otro")),
                "purchase_cost": total_cost,
                "purchased_quantity": quantity,
                "available_quantity": quantity,
                "unit_name": str(purchase.get("unit_name", "unidad")),
                "minimum_stock": float(purchase.get("minimum_stock", 0.0)),
            }
        )
    return updated_inventory


def render_suppliers() -> None:
    with st.container(border=True):
        render_page_header(
            "Proveedores",
            "Registra proveedores y consulta las compras asociadas.",
        )
        st.caption("Los proveedores se guardan durante la sesión y se incluyen en el respaldo general.")

    suppliers = _get_list("suppliers_registry")
    purchases = _get_list("purchases_registry")

    with st.form("supplier_form", clear_on_submit=True):
        columns = st.columns(2)
        with columns[0]:
            name = st.text_input("Nombre del proveedor", max_chars=120)
            phone = st.text_input("Teléfono", max_chars=40)
            email = st.text_input("Correo", max_chars=120)
        with columns[1]:
            address = st.text_input("Dirección", max_chars=180)
            products = st.text_input("Productos o categorías", max_chars=180)
            notes = st.text_area("Notas", max_chars=300)
        submitted = st.form_submit_button("Registrar proveedor", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("El nombre del proveedor es obligatorio.")
        else:
            suppliers.append(
                {
                    "supplier_id": uuid4().hex[:10],
                    "name": name.strip(),
                    "phone": phone.strip(),
                    "email": email.strip(),
                    "address": address.strip(),
                    "products": products.strip(),
                    "notes": notes.strip(),
                    "created_at_utc": _now(),
                }
            )
            _save_list("suppliers_registry", suppliers)
            st.success("Proveedor registrado.")
            st.rerun()

    st.divider()
    st.subheader("Proveedores registrados")
    if not suppliers:
        st.info("Todavía no hay proveedores registrados.")
        return

    for supplier in suppliers:
        supplier_purchases = [
            purchase
            for purchase in purchases
            if str(purchase.get("supplier_id", "")) == str(supplier.get("supplier_id", ""))
        ]
        total = sum(float(purchase.get("total", 0.0)) for purchase in supplier_purchases)
        pending = sum(1 for purchase in supplier_purchases if purchase.get("payment_status") != "Pagado")

        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {supplier.get('name', 'Proveedor')}")
                st.caption(
                    f"ID {supplier.get('supplier_id', '')} · "
                    f"{supplier.get('phone') or 'Sin teléfono'} · {supplier.get('email') or 'Sin correo'}"
                )
            with title_columns[1]:
                if st.button(
                    "Eliminar",
                    key=f"delete_supplier_{supplier.get('supplier_id')}",
                    use_container_width=True,
                ):
                    if supplier_purchases:
                        st.error("No puedes eliminar un proveedor con compras registradas.")
                    else:
                        _save_list(
                            "suppliers_registry",
                            [
                                item
                                for item in suppliers
                                if item.get("supplier_id") != supplier.get("supplier_id")
                            ],
                        )
                        st.rerun()

            metrics = st.columns(3)
            metrics[0].metric("Compras", str(len(supplier_purchases)))
            metrics[1].metric("Total comprado", format_money(total))
            metrics[2].metric("Pendientes", str(pending))

            render_info_card(
                "Ficha del proveedor",
                (
                    f"Dirección: {supplier.get('address') or 'No registrada'}. "
                    f"Productos: {supplier.get('products') or 'No registrados'}. "
                    f"Notas: {supplier.get('notes') or 'Sin notas'}."
                ),
                "PROVEEDOR",
            )


def render_purchases() -> None:
    with st.container(border=True):
        render_page_header(
            "Compras",
            "Registra compras y conéctalas con Inventario y Caja.",
        )
        st.caption(
            "Recibir una compra aumenta existencias; pagarla registra un egreso una sola vez."
        )

    suppliers = _get_list("suppliers_registry")
    purchases = _get_list("purchases_registry")
    inventory = _get_list("inventory_registry")
    cash = _get_list("cash_movements")

    supplier_options = {"Sin proveedor": ""}
    for supplier in suppliers:
        supplier_options[
            f"{supplier.get('name', 'Proveedor')} · {supplier.get('supplier_id', '')}"
        ] = str(supplier.get("supplier_id", ""))

    inventory_options = {"Crear material nuevo": ""}
    for item in inventory:
        inventory_options[
            f"{item.get('name', 'Material')} · {item.get('item_id', '')}"
        ] = str(item.get("item_id", ""))

    with st.form("purchase_form", clear_on_submit=True):
        first = st.columns(3)
        with first[0]:
            selected_supplier = st.selectbox("Proveedor", tuple(supplier_options.keys()))
        with first[1]:
            selected_inventory = st.selectbox("Material de inventario", tuple(inventory_options.keys()))
        with first[2]:
            material_name = st.text_input("Nombre del material", max_chars=120)

        second = st.columns(4)
        with second[0]:
            category = st.selectbox(
                "Categoría",
                ("Papel", "Tinta", "Adhesivo", "Sublimación", "Papelería", "Empaque", "Otro"),
            )
        with second[1]:
            quantity = st.number_input("Cantidad", min_value=0.01, value=1.0, step=1.0)
        with second[2]:
            unit_name = st.text_input("Unidad", value="unidad", max_chars=30)
        with second[3]:
            unit_cost = st.number_input("Costo unitario", min_value=0.0, value=0.0, step=0.5)

        third = st.columns(3)
        with third[0]:
            discount = st.number_input("Descuento", min_value=0.0, value=0.0, step=0.5)
        with third[1]:
            payment_status = st.selectbox("Pago", ("Pendiente", "Pagado", "Abono"))
        with third[2]:
            payment_method = st.selectbox(
                "Método de pago",
                ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro"),
            )

        minimum_stock = st.number_input("Existencia mínima para material nuevo", min_value=0.0, value=0.0)
        notes = st.text_area("Notas de la compra", max_chars=300)
        submitted = st.form_submit_button("Registrar compra", type="primary", use_container_width=True)

    if submitted:
        selected_item_id = inventory_options[selected_inventory]
        selected_item = next(
            (
                item
                for item in inventory
                if str(item.get("item_id", "")) == selected_item_id
            ),
            None,
        )
        resolved_name = (
            str(selected_item.get("name", ""))
            if selected_item is not None
            else material_name.strip()
        )
        resolved_unit = (
            str(selected_item.get("unit_name", "unidad"))
            if selected_item is not None
            else unit_name.strip()
        )
        subtotal = float(quantity) * float(unit_cost)
        total = max(subtotal - float(discount), 0.0)

        if not resolved_name:
            st.error("El nombre del material es obligatorio.")
        elif not resolved_unit:
            st.error("La unidad es obligatoria.")
        elif total <= 0:
            st.error("El total de la compra debe ser mayor que cero.")
        else:
            purchase_id = uuid4().hex[:10]
            purchases.append(
                {
                    "purchase_id": purchase_id,
                    "created_at_utc": _now(),
                    "supplier_id": supplier_options[selected_supplier],
                    "inventory_item_id": selected_item_id,
                    "material_name": resolved_name,
                    "category": category if selected_item is None else str(selected_item.get("category", category)),
                    "quantity": float(quantity),
                    "unit_name": resolved_unit,
                    "unit_cost": float(unit_cost),
                    "discount": float(discount),
                    "total": total,
                    "minimum_stock": float(minimum_stock),
                    "payment_status": payment_status,
                    "payment_method": payment_method,
                    "receipt_status": "Pendiente",
                    "inventory_applied": False,
                    "cash_registered": payment_status == "Pagado",
                    "notes": notes.strip(),
                }
            )
            if payment_status == "Pagado":
                cash.append(
                    {
                        "movement_id": uuid4().hex[:10],
                        "created_at_utc": _now(),
                        "movement_type": "Egreso",
                        "category": "Compra",
                        "amount": total,
                        "payment_method": payment_method,
                        "reference": purchase_id,
                        "notes": resolved_name,
                    }
                )
                _save_list("cash_movements", cash)
            _save_list("purchases_registry", purchases)
            st.success("Compra registrada.")
            st.rerun()

    st.divider()
    status_filter = st.selectbox(
        "Filtrar compras",
        ("Todas", "Pendiente", "Recibida", "Cancelada"),
    )
    filtered = purchases
    if status_filter != "Todas":
        filtered = [purchase for purchase in purchases if purchase.get("receipt_status") == status_filter]

    metrics = st.columns(4)
    metrics[0].metric("Compras", str(len(filtered)))
    metrics[1].metric(
        "Total",
        format_money(sum(float(purchase.get("total", 0.0)) for purchase in filtered)),
    )
    metrics[2].metric(
        "Pendientes de recibir",
        str(sum(1 for purchase in purchases if purchase.get("receipt_status") == "Pendiente")),
    )
    metrics[3].metric(
        "Pendientes de pago",
        str(sum(1 for purchase in purchases if purchase.get("payment_status") != "Pagado")),
    )

    if not filtered:
        st.info("No hay compras que coincidan con el filtro.")
        return

    for purchase in reversed(filtered):
        with st.container(border=True):
            st.markdown(f"### {purchase.get('material_name', 'Compra')}")
            st.caption(
                f"ID {purchase.get('purchase_id', '')} · "
                f"{_supplier_name(str(purchase.get('supplier_id', '')), suppliers)} · "
                f"{purchase.get('created_at_utc', '')}"
            )

            purchase_metrics = st.columns(5)
            purchase_metrics[0].metric(
                "Cantidad",
                f"{float(purchase.get('quantity', 0.0)):,.2f} {purchase.get('unit_name', 'unidad')}",
            )
            purchase_metrics[1].metric("Total", format_money(float(purchase.get("total", 0.0))))
            purchase_metrics[2].metric("Pago", str(purchase.get("payment_status", "Pendiente")))
            purchase_metrics[3].metric("Recepción", str(purchase.get("receipt_status", "Pendiente")))
            purchase_metrics[4].metric(
                "Inventario",
                "Actualizado" if purchase.get("inventory_applied") else "Pendiente",
            )

            actions = st.columns(3)
            if actions[0].button(
                "Marcar recibida",
                key=f"receive_purchase_{purchase.get('purchase_id')}",
                use_container_width=True,
                disabled=bool(purchase.get("inventory_applied"))
                or purchase.get("receipt_status") == "Cancelada",
            ):
                updated_inventory = _apply_purchase_to_inventory(purchase, inventory)
                updated_purchases = []
                for current in purchases:
                    updated = dict(current)
                    if current.get("purchase_id") == purchase.get("purchase_id"):
                        updated["receipt_status"] = "Recibida"
                        updated["inventory_applied"] = True
                    updated_purchases.append(updated)
                _save_list("inventory_registry", updated_inventory)
                _save_list("purchases_registry", updated_purchases)
                st.rerun()

            if actions[1].button(
                "Marcar pagada",
                key=f"pay_purchase_{purchase.get('purchase_id')}",
                use_container_width=True,
                disabled=bool(purchase.get("cash_registered"))
                or purchase.get("receipt_status") == "Cancelada",
            ):
                cash.append(
                    {
                        "movement_id": uuid4().hex[:10],
                        "created_at_utc": _now(),
                        "movement_type": "Egreso",
                        "category": "Compra",
                        "amount": float(purchase.get("total", 0.0)),
                        "payment_method": str(purchase.get("payment_method", "Otro")),
                        "reference": str(purchase.get("purchase_id", "")),
                        "notes": str(purchase.get("material_name", "Compra")),
                    }
                )
                updated_purchases = []
                for current in purchases:
                    updated = dict(current)
                    if current.get("purchase_id") == purchase.get("purchase_id"):
                        updated["payment_status"] = "Pagado"
                        updated["cash_registered"] = True
                    updated_purchases.append(updated)
                _save_list("cash_movements", cash)
                _save_list("purchases_registry", updated_purchases)
                st.rerun()

            if actions[2].button(
                "Cancelar",
                key=f"cancel_purchase_{purchase.get('purchase_id')}",
                use_container_width=True,
                disabled=bool(purchase.get("inventory_applied"))
                or bool(purchase.get("cash_registered"))
                or purchase.get("receipt_status") == "Cancelada",
            ):
                updated_purchases = []
                for current in purchases:
                    updated = dict(current)
                    if current.get("purchase_id") == purchase.get("purchase_id"):
                        updated["receipt_status"] = "Cancelada"
                    updated_purchases.append(updated)
                _save_list("purchases_registry", updated_purchases)
                st.rerun()

            render_info_card(
                "Notas",
                str(purchase.get("notes") or "Sin notas"),
                "COMPRA TEMPORAL",
            )
