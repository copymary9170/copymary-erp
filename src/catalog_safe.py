"""Capa de integridad para el catálogo y las producciones."""

import streamlit as st

from src import catalog


def aggregate_recipe(recipe: list[dict]) -> list[dict]:
    totals: dict[str, float] = {}
    for component in recipe:
        if not isinstance(component, dict):
            continue
        item_id = str(component.get("item_id", ""))
        quantity = float(component.get("quantity", 0.0))
        if item_id and quantity > 0:
            totals[item_id] = totals.get(item_id, 0.0) + quantity
    return [
        {"item_id": item_id, "quantity": quantity}
        for item_id, quantity in totals.items()
    ]


def _recipe_cost(recipe: list[dict], inventory: list[dict]) -> float:
    items = catalog._inventory_map(inventory)
    total = 0.0
    for component in aggregate_recipe(recipe):
        item = items.get(component["item_id"])
        if not item:
            continue
        purchased = max(float(item.get("purchased_quantity", 0.0)), 0.01)
        unit_cost = float(item.get("purchase_cost", 0.0)) / purchased
        total += unit_cost * component["quantity"]
    return total


def _max_producible(recipe: list[dict], inventory: list[dict]) -> float:
    consolidated = aggregate_recipe(recipe)
    if not consolidated:
        return 0.0
    items = catalog._inventory_map(inventory)
    capacities: list[float] = []
    for component in consolidated:
        item = items.get(component["item_id"])
        if not item:
            return 0.0
        capacities.append(
            float(item.get("available_quantity", 0.0)) // component["quantity"]
        )
    return min(capacities) if capacities else 0.0


def _can_produce(
    recipe: list[dict],
    inventory: list[dict],
    quantity: float,
) -> tuple[bool, str]:
    items = catalog._inventory_map(inventory)
    for component in aggregate_recipe(recipe):
        item = items.get(component["item_id"])
        if not item:
            return False, "La receta contiene un material que ya no existe."
        required = component["quantity"] * quantity
        if required > float(item.get("available_quantity", 0.0)):
            return False, f"No hay suficiente {item.get('name', 'material')}."
    return True, ""


def _apply_production(
    product: dict,
    quantity: float,
    inventory: list[dict],
    movements: list[dict],
) -> tuple[list[dict], list[dict]]:
    safe_product = dict(product)
    safe_product["recipe"] = aggregate_recipe(
        [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
    )
    return _original_apply_production(safe_product, quantity, inventory, movements)


def _save_list(key: str, items: list[dict]) -> None:
    if key == "products_registry":
        normalized: list[dict] = []
        for product in items:
            current = dict(product)
            current["recipe"] = aggregate_recipe(
                [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
            )
            normalized.append(current)
        st.session_state[key] = normalized
        return

    if key == "production_log":
        products = {
            str(product.get("product_id", "")): product
            for product in st.session_state.get("products_registry", [])
            if isinstance(product, dict)
        }
        enriched: list[dict] = []
        for production in items:
            current = dict(production)
            if not current.get("recipe_snapshot"):
                product = products.get(str(current.get("product_id", "")), {})
                current["recipe_snapshot"] = aggregate_recipe(
                    [dict(item) for item in product.get("recipe", []) if isinstance(item, dict)]
                )
            current.setdefault("reversed", False)
            enriched.append(current)
        st.session_state[key] = enriched
        return

    st.session_state[key] = items


_original_apply_production = catalog._apply_production


def render_safe_catalog() -> None:
    """Ejecuta el catálogo original con controles de integridad activados."""
    catalog._recipe_cost = _recipe_cost
    catalog._max_producible = _max_producible
    catalog._can_produce = _can_produce
    catalog._apply_production = _apply_production
    catalog._save_list = _save_list
    catalog.render_catalog()
