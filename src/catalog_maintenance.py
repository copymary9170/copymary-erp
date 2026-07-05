"""Mantenimiento de productos y recetas del catálogo."""

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _aggregate(recipe: list[dict]) -> list[dict]:
    totals: dict[str, float] = {}
    for component in recipe:
        item_id = str(component.get("item_id", ""))
        quantity = float(component.get("quantity", 0.0))
        if item_id and quantity > 0:
            totals[item_id] = totals.get(item_id, 0.0) + quantity
    return [{"item_id": item_id, "quantity": quantity} for item_id, quantity in totals.items()]


def render_catalog_maintenance() -> None:
    with st.container(border=True):
        render_page_header("Mantenimiento del catálogo", "Consolida recetas repetidas y edita productos registrados.")
        st.caption("Evita que un material repetido se descuente incorrectamente durante la producción.")

    products = _rows("products_registry")
    inventory = _rows("inventory_registry")
    names = {str(item.get("item_id", "")): str(item.get("name", "Material")) for item in inventory}
    duplicate_count = sum(
        1
        for product in products
        if len(product.get("recipe", [])) != len(_aggregate(product.get("recipe", [])))
    )

    metrics = st.columns(3)
    metrics[0].metric("Productos y servicios", str(len(products)))
    metrics[1].metric("Recetas duplicadas", str(duplicate_count))
    metrics[2].metric("Materiales", str(len(inventory)))

    if duplicate_count:
        if st.button("Consolidar recetas duplicadas", type="primary", use_container_width=True):
            updated = []
            for product in products:
                current = dict(product)
                current["recipe"] = _aggregate([dict(item) for item in product.get("recipe", []) if isinstance(item, dict)])
                updated.append(current)
            st.session_state["products_registry"] = updated
            st.success("Las recetas fueron consolidadas.")
            st.rerun()
    else:
        st.success("No hay materiales repetidos dentro de las recetas.")

    for product in products:
        product_id = str(product.get("product_id", ""))
        recipe = _aggregate([dict(item) for item in product.get("recipe", []) if isinstance(item, dict)])
        with st.container(border=True):
            st.markdown(f"### {product.get('name', 'Producto')}")
            header = st.columns(3)
            header[0].metric("Precio", format_money(float(product.get("sale_price", 0.0))))
            header[1].metric("Otros costos", format_money(float(product.get("extra_cost", 0.0))))
            header[2].metric("Componentes", str(len(recipe)))

            if recipe:
                for component in recipe:
                    st.write(f"- {names.get(component['item_id'], 'Material no disponible')}: {component['quantity']:,.2f}")

            with st.form(f"catalog_maintenance_{product_id}"):
                columns = st.columns(3)
                name = columns[0].text_input("Nombre", value=str(product.get("name", "")), key=f"cm_name_{product_id}")
                price = columns[1].number_input("Precio", min_value=0.0, value=float(product.get("sale_price", 0.0)), step=0.5, key=f"cm_price_{product_id}")
                extra = columns[2].number_input("Otros costos", min_value=0.0, value=float(product.get("extra_cost", 0.0)), step=0.1, key=f"cm_extra_{product_id}")
                notes = st.text_input("Notas", value=str(product.get("notes", "")), key=f"cm_notes_{product_id}")
                save = st.form_submit_button("Guardar cambios", use_container_width=True)

            if save:
                updated = []
                for current in products:
                    item = dict(current)
                    if str(current.get("product_id", "")) == product_id:
                        item["name"] = name.strip()
                        item["sale_price"] = float(price)
                        item["extra_cost"] = float(extra)
                        item["notes"] = notes.strip()
                        item["recipe"] = recipe
                    updated.append(item)
                st.session_state["products_registry"] = updated
                st.rerun()

    render_info_card("Protección", "Las recetas consolidadas usan una sola línea por material con la cantidad total requerida.", "INTEGRIDAD DEL CATÁLOGO")
