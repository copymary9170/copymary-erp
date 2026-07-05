"""Catálogo temporal de productos, servicios y recetas de producción."""

import csv
from datetime import datetime, timezone
from io import StringIO
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


def _inventory_map(inventory: list[dict]) -> dict[str, dict]:
    return {str(item.get("item_id", "")): item for item in inventory}


def _recipe_cost(recipe: list[dict], inventory: list[dict]) -> float:
    items = _inventory_map(inventory)
    total = 0.0
    for component in recipe:
        item = items.get(str(component.get("item_id", "")))
        if not item:
            continue
        purchased = max(float(item.get("purchased_quantity", 1.0)), 0.01)
        unit_cost = float(item.get("purchase_cost", 0.0)) / purchased
        total += unit_cost * float(component.get("quantity", 0.0))
    return total


def _max_producible(recipe: list[dict], inventory: list[dict]) -> float:
    if not recipe:
        return 0.0
    items = _inventory_map(inventory)
    capacities: list[float] = []
    for component in recipe:
        required = float(component.get("quantity", 0.0))
        item = items.get(str(component.get("item_id", "")))
        if not item or required <= 0:
            return 0.0
        capacities.append(float(item.get("available_quantity", 0.0)) // required)
    return min(capacities) if capacities else 0.0


def _can_produce(recipe: list[dict], inventory: list[dict], quantity: float) -> tuple[bool, str]:
    items = _inventory_map(inventory)
    for component in recipe:
        item = items.get(str(component.get("item_id", "")))
        if not item:
            return False, "La receta contiene un material que ya no existe."
        required = float(component.get("quantity", 0.0)) * quantity
        available = float(item.get("available_quantity", 0.0))
        if required > available:
            return False, f"No hay suficiente {item.get('name', 'material')}."
    return True, ""


def _apply_production(
    product: dict,
    quantity: float,
    inventory: list[dict],
    movements: list[dict],
) -> tuple[list[dict], list[dict]]:
    recipe = [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
    required_by_id = {
        str(component.get("item_id", "")): float(component.get("quantity", 0.0)) * quantity
        for component in recipe
    }
    updated_inventory: list[dict] = []
    for item in inventory:
        updated = dict(item)
        item_id = str(item.get("item_id", ""))
        if item_id in required_by_id:
            previous = float(item.get("available_quantity", 0.0))
            consumed = required_by_id[item_id]
            resulting = previous - consumed
            updated["available_quantity"] = resulting
            movements.append(
                {
                    "movement_id": uuid4().hex[:10],
                    "created_at_utc": _now(),
                    "item_id": item_id,
                    "item_name": str(item.get("name", "Material")),
                    "movement_type": "Salida",
                    "quantity": consumed,
                    "unit_name": str(item.get("unit_name", "unidad")),
                    "reason": f"Producción de {quantity:,.2f} × {product.get('name', 'producto')}",
                    "previous_quantity": previous,
                    "resulting_quantity": resulting,
                }
            )
        updated_inventory.append(updated)
    return updated_inventory, movements


def _catalog_csv(products: list[dict], inventory: list[dict]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(
        [
            "ID",
            "Código",
            "Nombre",
            "Tipo",
            "Categoría",
            "Precio de venta",
            "Costo calculado",
            "Ganancia estimada",
            "Componentes",
            "Activo",
        ]
    )
    for product in products:
        cost = _recipe_cost(product.get("recipe", []), inventory)
        writer.writerow(
            [
                product.get("product_id", ""),
                product.get("sku", ""),
                product.get("name", ""),
                product.get("product_type", ""),
                product.get("category", ""),
                f"{float(product.get('sale_price', 0.0)):.4f}",
                f"{cost:.4f}",
                f"{float(product.get('sale_price', 0.0)) - cost:.4f}",
                len(product.get("recipe", [])),
                "Sí" if product.get("active", True) else "No",
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def render_catalog() -> None:
    with st.container(border=True):
        render_page_header(
            "Catálogo y producción",
            "Crea productos y servicios, define recetas y descuenta materiales al producir.",
        )
        st.caption("El catálogo, las recetas y las producciones son temporales y se incluyen en el respaldo general.")

    products = _get_list("products_registry")
    inventory = _get_list("inventory_registry")
    movements = _get_list("inventory_movements")
    production_log = _get_list("production_log")

    inventory_labels = {
        f"{item.get('name', 'Material')} · {item.get('item_id', '')}": str(item.get("item_id", ""))
        for item in inventory
    }

    with st.form("catalog_product_form", clear_on_submit=True):
        first = st.columns(4)
        with first[0]:
            sku = st.text_input("Código o SKU", max_chars=40)
        with first[1]:
            name = st.text_input("Nombre", max_chars=120)
        with first[2]:
            product_type = st.selectbox("Tipo", ("Producto", "Servicio"))
        with first[3]:
            category = st.selectbox(
                "Categoría",
                ("Impresión", "Papelería", "Sublimación", "Manualidad", "Diseño", "Servicio", "Otro"),
            )

        second = st.columns(3)
        with second[0]:
            sale_price = st.number_input("Precio de venta", min_value=0.0, value=0.0, step=0.5)
        with second[1]:
            extra_cost = st.number_input("Otros costos por unidad", min_value=0.0, value=0.0, step=0.1)
        with second[2]:
            notes = st.text_input("Notas", max_chars=180)

        recipe: list[dict] = []
        if product_type == "Producto" and inventory:
            st.markdown("#### Receta de materiales")
            options = ("Sin material", *inventory_labels.keys())
            for index in range(1, 6):
                columns = st.columns([3, 1])
                with columns[0]:
                    selected = st.selectbox(
                        f"Material {index}",
                        options,
                        key=f"catalog_material_{index}",
                    )
                with columns[1]:
                    required = st.number_input(
                        f"Cantidad {index}",
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                        key=f"catalog_required_{index}",
                    )
                if selected != "Sin material" and required > 0:
                    recipe.append(
                        {
                            "item_id": inventory_labels[selected],
                            "quantity": float(required),
                        }
                    )
        elif product_type == "Producto":
            st.info("Registra materiales en Inventario antes de crear una receta.")

        submitted = st.form_submit_button("Registrar en catálogo", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("El nombre es obligatorio.")
        elif sale_price <= 0:
            st.error("El precio de venta debe ser mayor que cero.")
        elif product_type == "Producto" and not recipe:
            st.error("Un producto debe tener al menos un material en su receta.")
        else:
            products.append(
                {
                    "product_id": uuid4().hex[:10],
                    "created_at_utc": _now(),
                    "sku": sku.strip(),
                    "name": name.strip(),
                    "product_type": product_type,
                    "category": category,
                    "sale_price": float(sale_price),
                    "extra_cost": float(extra_cost),
                    "notes": notes.strip(),
                    "recipe": recipe,
                    "active": True,
                }
            )
            _save_list("products_registry", products)
            st.success("Producto o servicio registrado.")
            st.rerun()

    st.divider()
    metrics = st.columns(4)
    metrics[0].metric("Registros", str(len(products)))
    metrics[1].metric("Productos", str(sum(1 for item in products if item.get("product_type") == "Producto")))
    metrics[2].metric("Servicios", str(sum(1 for item in products if item.get("product_type") == "Servicio")))
    metrics[3].metric("Producciones", str(len(production_log)))

    st.download_button(
        "Descargar catálogo CSV",
        data=_catalog_csv(products, inventory),
        file_name="copymary_catalogo.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not products,
    )

    if not products:
        st.info("Todavía no hay productos o servicios registrados.")
        return

    for product in products:
        recipe = [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
        recipe_cost = _recipe_cost(recipe, inventory)
        total_cost = recipe_cost + float(product.get("extra_cost", 0.0))
        profit = float(product.get("sale_price", 0.0)) - total_cost
        max_units = _max_producible(recipe, inventory) if product.get("product_type") == "Producto" else 0

        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {product.get('name', 'Producto')}")
                st.caption(
                    f"{product.get('product_type', '')} · {product.get('category', '')} · "
                    f"SKU {product.get('sku') or 'Sin código'} · ID {product.get('product_id', '')}"
                )
            with title_columns[1]:
                if st.button(
                    "Eliminar",
                    key=f"delete_product_{product.get('product_id')}",
                    use_container_width=True,
                ):
                    _save_list(
                        "products_registry",
                        [item for item in products if item.get("product_id") != product.get("product_id")],
                    )
                    st.rerun()

            product_metrics = st.columns(4)
            product_metrics[0].metric("Precio", format_money(float(product.get("sale_price", 0.0))))
            product_metrics[1].metric("Costo calculado", format_money(total_cost))
            product_metrics[2].metric("Ganancia estimada", format_money(profit))
            product_metrics[3].metric(
                "Producción posible",
                f"{max_units:,.0f}" if product.get("product_type") == "Producto" else "No aplica",
            )

            if recipe:
                names = _inventory_map(inventory)
                st.markdown("**Receta:**")
                for component in recipe:
                    item = names.get(str(component.get("item_id", "")), {})
                    st.write(
                        f"- {item.get('name', 'Material no disponible')}: "
                        f"{float(component.get('quantity', 0.0)):,.2f} {item.get('unit_name', 'unidad')}"
                    )

            if product.get("product_type") == "Producto":
                production_columns = st.columns([2, 1])
                with production_columns[0]:
                    quantity_to_produce = st.number_input(
                        "Cantidad a producir",
                        min_value=1.0,
                        value=1.0,
                        step=1.0,
                        key=f"produce_quantity_{product.get('product_id')}",
                    )
                with production_columns[1]:
                    produce = st.button(
                        "Registrar producción",
                        key=f"produce_{product.get('product_id')}",
                        use_container_width=True,
                    )

                if produce:
                    can_produce, message = _can_produce(recipe, inventory, float(quantity_to_produce))
                    if not can_produce:
                        st.error(message)
                    else:
                        updated_inventory, updated_movements = _apply_production(
                            product,
                            float(quantity_to_produce),
                            inventory,
                            movements,
                        )
                        production_log.append(
                            {
                                "production_id": uuid4().hex[:10],
                                "created_at_utc": _now(),
                                "product_id": str(product.get("product_id", "")),
                                "product_name": str(product.get("name", "Producto")),
                                "quantity": float(quantity_to_produce),
                                "unit_cost": total_cost,
                                "total_cost": total_cost * float(quantity_to_produce),
                            }
                        )
                        _save_list("inventory_registry", updated_inventory)
                        _save_list("inventory_movements", updated_movements)
                        _save_list("production_log", production_log)
                        st.success("Producción registrada e inventario actualizado.")
                        st.rerun()

            render_info_card(
                "Descripción",
                str(product.get("notes") or "Sin notas"),
                "CATÁLOGO TEMPORAL",
            )

    st.divider()
    st.subheader("Historial de producción")
    if not production_log:
        st.info("Todavía no hay producciones registradas.")
    else:
        for production in reversed(production_log):
            with st.container(border=True):
                columns = st.columns(4)
                columns[0].metric("Producto", str(production.get("product_name", "")))
                columns[1].metric("Cantidad", f"{float(production.get('quantity', 0.0)):,.2f}")
                columns[2].metric("Costo unitario", format_money(float(production.get("unit_cost", 0.0))))
                columns[3].metric("Costo total", format_money(float(production.get("total_cost", 0.0))))
                st.caption(
                    f"ID {production.get('production_id', '')} · {production.get('created_at_utc', '')}"
                )
