"""Protecciones contra eliminaciones que rompan el historial del ERP."""

import streamlit as st

from src import catalog_safe, inventory


_original_inventory_save = inventory._save_items
_original_catalog_save = catalog_safe._save_list


def _dict_rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _material_dependencies(item_id: str) -> list[str]:
    dependencies: list[str] = []

    for product in _dict_rows("products_registry"):
        for component in product.get("recipe", []):
            if isinstance(component, dict) and str(component.get("item_id", "")) == item_id:
                dependencies.append(f"receta de {product.get('name', 'producto')}")
                break

    if any(str(item.get("inventory_item_id", "")) == item_id for item in _dict_rows("purchases_registry")):
        dependencies.append("compras registradas")

    if any(str(item.get("item_id", "")) == item_id for item in _dict_rows("inventory_movements")):
        dependencies.append("historial de movimientos")

    for production in _dict_rows("production_log"):
        snapshot = production.get("recipe_snapshot", [])
        if any(
            isinstance(component, dict)
            and str(component.get("item_id", "")) == item_id
            for component in snapshot
        ):
            dependencies.append("producciones registradas")
            break

    return sorted(set(dependencies))


def _product_dependencies(product_id: str) -> list[str]:
    dependencies: list[str] = []
    if any(str(item.get("product_id", "")) == product_id for item in _dict_rows("production_log")):
        dependencies.append("historial de producción")
    return dependencies


def _protected_inventory_save(items) -> None:
    current = inventory._get_items()
    current_ids = {str(item.item_id) for item in current}
    new_ids = {str(item.item_id) for item in items}
    removed = current_ids - new_ids

    blocked: list[str] = []
    for item_id in removed:
        dependencies = _material_dependencies(item_id)
        if dependencies:
            item = next((row for row in current if str(row.item_id) == item_id), None)
            name = item.name if item else item_id
            blocked.append(f"{name}: {', '.join(dependencies)}")

    if blocked:
        st.error("No se puede eliminar porque existen dependencias: " + " | ".join(blocked))
        st.stop()

    _original_inventory_save(items)


def _protected_catalog_save(key: str, items: list[dict]) -> None:
    if key == "products_registry":
        current = _dict_rows("products_registry")
        current_ids = {str(item.get("product_id", "")) for item in current}
        new_ids = {str(item.get("product_id", "")) for item in items}
        removed = current_ids - new_ids

        blocked: list[str] = []
        for product_id in removed:
            dependencies = _product_dependencies(product_id)
            if dependencies:
                product = next(
                    (item for item in current if str(item.get("product_id", "")) == product_id),
                    {},
                )
                blocked.append(
                    f"{product.get('name', product_id)}: {', '.join(dependencies)}"
                )

        if blocked:
            st.error("No se puede eliminar porque existen dependencias: " + " | ".join(blocked))
            st.stop()

    _original_catalog_save(key, items)


def activate_deletion_protection() -> None:
    """Activa las protecciones antes de renderizar Inventario y Catálogo."""
    inventory._save_items = _protected_inventory_save
    catalog_safe._save_list = _protected_catalog_save
