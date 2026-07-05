"""Inventario temporal de materiales para CopyMary ERP."""

from dataclasses import asdict, dataclass, replace
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header


@dataclass(frozen=True)
class InventoryItem:
    item_id: str
    name: str
    category: str
    purchase_cost: float
    purchased_quantity: float
    available_quantity: float
    unit_name: str
    minimum_stock: float

    @property
    def unit_cost(self) -> float:
        return self.purchase_cost / self.purchased_quantity

    @property
    def stock_value(self) -> float:
        return self.available_quantity * self.unit_cost

    @property
    def is_low_stock(self) -> bool:
        return self.available_quantity <= self.minimum_stock


def _format_money(value: float) -> str:
    return f"$ {value:,.2f}"


def _get_items() -> list[InventoryItem]:
    raw_items = st.session_state.get("inventory_registry", [])
    items: list[InventoryItem] = []
    for raw_item in raw_items:
        if isinstance(raw_item, InventoryItem):
            items.append(raw_item)
        elif isinstance(raw_item, dict):
            items.append(InventoryItem(**raw_item))
    return items


def _save_items(items: list[InventoryItem]) -> None:
    st.session_state.inventory_registry = [asdict(item) for item in items]


def _adjust_stock(
    items: list[InventoryItem], item_id: str, movement: str, quantity: float
) -> list[InventoryItem]:
    updated_items: list[InventoryItem] = []
    for item in items:
        if item.item_id != item_id:
            updated_items.append(item)
            continue

        if movement == "Entrada":
            new_quantity = item.available_quantity + quantity
        else:
            new_quantity = max(item.available_quantity - quantity, 0.0)
        updated_items.append(replace(item, available_quantity=new_quantity))
    return updated_items


def render_inventory() -> None:
    """Renderiza el inventario temporal de materiales."""
    with st.container(border=True):
        render_page_header(
            "Inventario",
            "Registra materiales, calcula su costo unitario y controla existencias durante la sesión.",
        )
        st.caption("Los registros se conservan únicamente mientras la sesión permanezca abierta.")

    st.warning(
        "Este inventario todavía no usa base de datos. Los materiales y movimientos pueden perderse al reiniciar la aplicación."
    )

    items = _get_items()

    st.subheader("Registrar material")
    with st.form("inventory_item_form", clear_on_submit=True):
        first_row = st.columns(3)
        with first_row[0]:
            name = st.text_input("Nombre del material", max_chars=100)
        with first_row[1]:
            category = st.selectbox(
                "Categoría",
                ("Papel", "Tinta", "Adhesivo", "Sublimación", "Papelería", "Empaque", "Otro"),
            )
        with first_row[2]:
            unit_name = st.text_input(
                "Unidad de control",
                value="unidad",
                max_chars=30,
                help="Ejemplos: hoja, unidad, ml, metro o pliego.",
            )

        second_row = st.columns(3)
        with second_row[0]:
            purchase_cost = st.number_input(
                "Costo total de compra",
                min_value=0.0,
                value=0.0,
                step=1.0,
            )
        with second_row[1]:
            purchased_quantity = st.number_input(
                "Cantidad comprada",
                min_value=0.01,
                value=1.0,
                step=1.0,
            )
        with second_row[2]:
            minimum_stock = st.number_input(
                "Existencia mínima",
                min_value=0.0,
                value=0.0,
                step=1.0,
            )

        submitted = st.form_submit_button(
            "Registrar material",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        cleaned_name = name.strip()
        cleaned_unit = unit_name.strip()
        if not cleaned_name:
            st.error("El nombre del material no puede quedar vacío.")
        elif not cleaned_unit:
            st.error("La unidad de control no puede quedar vacía.")
        elif purchase_cost <= 0:
            st.error("El costo total de compra debe ser mayor que cero.")
        else:
            items.append(
                InventoryItem(
                    item_id=uuid4().hex[:8],
                    name=cleaned_name,
                    category=category,
                    purchase_cost=float(purchase_cost),
                    purchased_quantity=float(purchased_quantity),
                    available_quantity=float(purchased_quantity),
                    unit_name=cleaned_unit,
                    minimum_stock=float(minimum_stock),
                )
            )
            _save_items(items)
            st.success("Material registrado durante esta sesión.")
            st.rerun()

    st.divider()
    st.subheader("Resumen de inventario")
    total_value = sum(item.stock_value for item in items)
    low_stock_count = sum(1 for item in items if item.is_low_stock)
    summary_columns = st.columns(3)
    summary_columns[0].metric("Materiales registrados", str(len(items)))
    summary_columns[1].metric("Valor disponible", _format_money(total_value))
    summary_columns[2].metric("Existencias bajas", str(low_stock_count))

    if not items:
        st.info("Todavía no hay materiales registrados en esta sesión.")
        return

    st.subheader("Materiales disponibles")
    for item in items:
        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {item.name}")
                st.caption(f"{item.category} · ID {item.item_id}")
            with title_columns[1]:
                if st.button("Eliminar", key=f"delete_item_{item.item_id}", use_container_width=True):
                    _save_items([current for current in items if current.item_id != item.item_id])
                    st.rerun()

            metric_columns = st.columns(4)
            metric_columns[0].metric("Costo unitario", _format_money(item.unit_cost))
            metric_columns[1].metric(
                "Existencia",
                f"{item.available_quantity:,.2f} {item.unit_name}",
            )
            metric_columns[2].metric("Valor disponible", _format_money(item.stock_value))
            metric_columns[3].metric(
                "Estado",
                "BAJO" if item.is_low_stock else "DISPONIBLE",
            )

            if item.is_low_stock:
                st.warning(
                    f"La existencia alcanzó el mínimo definido de {item.minimum_stock:,.2f} {item.unit_name}."
                )

            with st.form(f"stock_movement_form_{item.item_id}", clear_on_submit=True):
                movement_columns = st.columns(3)
                with movement_columns[0]:
                    movement = st.selectbox(
                        "Movimiento",
                        ("Entrada", "Salida"),
                        key=f"movement_{item.item_id}",
                    )
                with movement_columns[1]:
                    movement_quantity = st.number_input(
                        f"Cantidad en {item.unit_name}",
                        min_value=0.01,
                        value=1.0,
                        step=1.0,
                        key=f"movement_quantity_{item.item_id}",
                    )
                with movement_columns[2]:
                    movement_submitted = st.form_submit_button(
                        "Aplicar movimiento",
                        type="primary",
                        use_container_width=True,
                    )

            if movement_submitted:
                if movement == "Salida" and movement_quantity > item.available_quantity:
                    st.error("La salida no puede superar la existencia disponible.")
                else:
                    _save_items(
                        _adjust_stock(
                            items,
                            item_id=item.item_id,
                            movement=movement,
                            quantity=float(movement_quantity),
                        )
                    )
                    st.rerun()

            render_info_card(
                "Costo utilizable en Costeo",
                (
                    f"Cada {item.unit_name} de {item.name} tiene un costo orientativo de "
                    f"{_format_money(item.unit_cost)}."
                ),
                "COSTO UNITARIO",
            )
