"""Módulo temporal de costeo conectado con configuración, activos e inventario."""

from dataclasses import asdict, dataclass
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header


@dataclass(frozen=True)
class CostingResult:
    material_cost: float
    ink_cost: float
    labor_cost: float
    indirect_cost: float
    asset_cost: float
    other_cost: float
    quantity: int
    unit_cost: float
    unit_price: float
    total_cost: float
    total_price: float
    estimated_profit: float


@dataclass(frozen=True)
class SavedPrice:
    price_id: str
    name: str
    material_label: str
    asset_label: str
    currency: str
    profit_margin: float
    unit_cost: float
    unit_price: float


def _format_money(value: float, currency: str) -> str:
    symbols = {"USD": "$", "VES": "Bs", "EUR": "€"}
    symbol = symbols.get(currency, currency)
    return f"{symbol} {value:,.2f}"


def _get_settings() -> tuple[str, float, float]:
    settings = st.session_state.get("general_settings")
    if settings is None:
        return "USD", 40.0, 0.0
    currency = getattr(settings, "currency", "USD")
    profit_margin = float(getattr(settings, "profit_margin", 40.0))
    fixed_cost_per_unit = float(getattr(settings, "fixed_cost_per_unit", 0.0))
    return currency, profit_margin, fixed_cost_per_unit


def _get_assets() -> list[dict]:
    raw_assets = st.session_state.get("assets_registry", [])
    assets: list[dict] = []
    for raw_asset in raw_assets:
        if isinstance(raw_asset, dict):
            assets.append(raw_asset)
        else:
            assets.append(
                {
                    "asset_id": getattr(raw_asset, "asset_id", ""),
                    "name": getattr(raw_asset, "name", "Equipo"),
                    "acquisition_cost": float(getattr(raw_asset, "acquisition_cost", 0.0)),
                    "lifetime_units": int(getattr(raw_asset, "lifetime_units", 1)),
                }
            )
    return assets


def _get_inventory_items() -> list[dict]:
    raw_items = st.session_state.get("inventory_registry", [])
    items: list[dict] = []
    for raw_item in raw_items:
        if isinstance(raw_item, dict):
            items.append(raw_item)
        else:
            items.append(
                {
                    "item_id": getattr(raw_item, "item_id", ""),
                    "name": getattr(raw_item, "name", "Material"),
                    "purchase_cost": float(getattr(raw_item, "purchase_cost", 0.0)),
                    "purchased_quantity": float(getattr(raw_item, "purchased_quantity", 1.0)),
                    "unit_name": getattr(raw_item, "unit_name", "unidad"),
                }
            )
    return items


def _get_saved_prices() -> list[SavedPrice]:
    raw_prices = st.session_state.get("saved_prices", [])
    prices: list[SavedPrice] = []
    for raw_price in raw_prices:
        if isinstance(raw_price, SavedPrice):
            prices.append(raw_price)
        elif isinstance(raw_price, dict):
            prices.append(SavedPrice(**raw_price))
    return prices


def _save_prices(prices: list[SavedPrice]) -> None:
    st.session_state.saved_prices = [asdict(price) for price in prices]


def _asset_depreciation(asset: dict) -> float:
    lifetime_units = max(int(asset.get("lifetime_units", 1)), 1)
    return float(asset.get("acquisition_cost", 0.0)) / lifetime_units


def _inventory_unit_cost(item: dict) -> float:
    purchased_quantity = max(float(item.get("purchased_quantity", 1.0)), 0.01)
    return float(item.get("purchase_cost", 0.0)) / purchased_quantity


def _calculate_result(
    material_cost: float,
    ink_cost: float,
    labor_cost: float,
    indirect_cost: float,
    asset_cost: float,
    other_cost: float,
    quantity: int,
    profit_margin: float,
) -> CostingResult:
    unit_cost = material_cost + ink_cost + labor_cost + indirect_cost + asset_cost + other_cost
    unit_price = unit_cost * (1 + profit_margin / 100)
    total_cost = unit_cost * quantity
    total_price = unit_price * quantity
    return CostingResult(
        material_cost=material_cost,
        ink_cost=ink_cost,
        labor_cost=labor_cost,
        indirect_cost=indirect_cost,
        asset_cost=asset_cost,
        other_cost=other_cost,
        quantity=quantity,
        unit_cost=unit_cost,
        unit_price=unit_price,
        total_cost=total_cost,
        total_price=total_price,
        estimated_profit=total_price - total_cost,
    )


def render_costing() -> None:
    """Renderiza costeo y lista temporal de precios."""
    with st.container(border=True):
        render_page_header(
            "Costeo",
            "Calcula precios y guarda resultados temporales como lista de precios.",
        )
        st.caption("Los cálculos y precios guardados se conservan únicamente durante la sesión actual.")

    st.warning(
        "Este módulo todavía no utiliza base de datos. La configuración, los activos, el inventario y los precios guardados pueden perderse al reiniciar."
    )

    currency, profit_margin, fixed_cost_per_unit = _get_settings()
    assets = _get_assets()
    inventory_items = _get_inventory_items()
    saved_prices = _get_saved_prices()

    status_columns = st.columns(4)
    status_columns[0].metric("Moneda", currency)
    status_columns[1].metric("Margen configurado", f"{profit_margin:.0f}%")
    status_columns[2].metric("Costo fijo sugerido", _format_money(fixed_cost_per_unit, currency))
    status_columns[3].metric("Precios guardados", str(len(saved_prices)))

    st.subheader("Calcular precio")
    asset_labels = ["Sin equipo registrado"] + [
        f"{asset.get('name', 'Equipo')} · {asset.get('asset_id', '')}" for asset in assets
    ]
    material_labels = ["Costo manual"] + [
        f"{item.get('name', 'Material')} · {item.get('item_id', '')}" for item in inventory_items
    ]

    with st.form("connected_costing_form"):
        selector_columns = st.columns(2)
        with selector_columns[0]:
            selected_material_label = st.selectbox("Material principal", material_labels)
        with selector_columns[1]:
            selected_asset_label = st.selectbox("Equipo utilizado", asset_labels)

        selected_material_cost = 0.0
        selected_material_unit = "unidad"
        if selected_material_label != "Costo manual":
            selected_material_index = material_labels.index(selected_material_label) - 1
            selected_material = inventory_items[selected_material_index]
            selected_material_cost = _inventory_unit_cost(selected_material)
            selected_material_unit = str(selected_material.get("unit_name", "unidad"))

        selected_asset_cost = 0.0
        if selected_asset_label != "Sin equipo registrado":
            selected_asset_index = asset_labels.index(selected_asset_label) - 1
            selected_asset_cost = _asset_depreciation(assets[selected_asset_index])

        first_row = st.columns(3)
        with first_row[0]:
            material_cost = st.number_input(
                f"Material por unidad de venta ({selected_material_unit})",
                min_value=0.0,
                value=selected_material_cost,
                step=0.01,
                format="%.3f",
            )
        with first_row[1]:
            ink_cost = st.number_input(
                "Tinta por unidad",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
            )
        with first_row[2]:
            labor_cost = st.number_input(
                "Mano de obra por unidad",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
            )

        second_row = st.columns(4)
        with second_row[0]:
            indirect_cost = st.number_input(
                "Gastos indirectos por unidad",
                min_value=0.0,
                value=fixed_cost_per_unit,
                step=0.01,
                format="%.2f",
            )
        with second_row[1]:
            asset_cost = st.number_input(
                "Depreciación del equipo por unidad",
                min_value=0.0,
                value=selected_asset_cost,
                step=0.001,
                format="%.3f",
            )
        with second_row[2]:
            other_cost = st.number_input(
                "Otros costos por unidad",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
            )
        with second_row[3]:
            quantity = st.number_input("Cantidad", min_value=1, value=1, step=1)

        submitted = st.form_submit_button(
            "Calcular costo y precio",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state.connected_costing_result = _calculate_result(
            material_cost=float(material_cost),
            ink_cost=float(ink_cost),
            labor_cost=float(labor_cost),
            indirect_cost=float(indirect_cost),
            asset_cost=float(asset_cost),
            other_cost=float(other_cost),
            quantity=int(quantity),
            profit_margin=profit_margin,
        )
        st.session_state.connected_costing_asset = selected_asset_label
        st.session_state.connected_costing_material = selected_material_label
        st.session_state.pop("save_price_name", None)

    result = st.session_state.get("connected_costing_result")
    if result is not None:
        st.divider()
        st.subheader("Resultado")
        result_columns = st.columns(4)
        result_columns[0].metric("Costo por unidad", _format_money(result.unit_cost, currency))
        result_columns[1].metric("Precio por unidad", _format_money(result.unit_price, currency))
        result_columns[2].metric("Venta total", _format_money(result.total_price, currency))
        result_columns[3].metric("Ganancia estimada", _format_money(result.estimated_profit, currency))

        detail_columns = st.columns(2)
        with detail_columns[0]:
            render_info_card(
                "Costos directos",
                (
                    f"Material: {_format_money(result.material_cost, currency)} · "
                    f"Tinta: {_format_money(result.ink_cost, currency)} · "
                    f"Mano de obra: {_format_money(result.labor_cost, currency)}"
                ),
                "POR UNIDAD",
            )
        with detail_columns[1]:
            render_info_card(
                "Costos complementarios",
                (
                    f"Indirectos: {_format_money(result.indirect_cost, currency)} · "
                    f"Equipo: {_format_money(result.asset_cost, currency)} · "
                    f"Otros: {_format_money(result.other_cost, currency)}"
                ),
                "POR UNIDAD",
            )

        st.subheader("Guardar en lista de precios")
        with st.form("save_price_form", clear_on_submit=True):
            price_name = st.text_input(
                "Nombre del producto o servicio",
                max_chars=100,
                placeholder="Ejemplo: Impresión color en papel fotográfico",
            )
            save_submitted = st.form_submit_button(
                "Guardar precio temporal",
                type="primary",
                use_container_width=True,
            )

        if save_submitted:
            cleaned_name = price_name.strip()
            if not cleaned_name:
                st.error("Debes escribir un nombre para guardar el precio.")
            else:
                saved_prices.append(
                    SavedPrice(
                        price_id=uuid4().hex[:8],
                        name=cleaned_name,
                        material_label=st.session_state.get("connected_costing_material", "Costo manual"),
                        asset_label=st.session_state.get("connected_costing_asset", "Sin equipo registrado"),
                        currency=currency,
                        profit_margin=profit_margin,
                        unit_cost=result.unit_cost,
                        unit_price=result.unit_price,
                    )
                )
                _save_prices(saved_prices)
                st.success("Precio guardado durante esta sesión.")
                st.rerun()

    st.divider()
    st.subheader("Lista temporal de precios")
    saved_prices = _get_saved_prices()
    if not saved_prices:
        st.info("Todavía no hay precios guardados en esta sesión.")
        return

    for saved_price in saved_prices:
        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {saved_price.name}")
                st.caption(f"ID {saved_price.price_id} · Margen {saved_price.profit_margin:.0f}%")
            with title_columns[1]:
                if st.button(
                    "Eliminar",
                    key=f"delete_price_{saved_price.price_id}",
                    use_container_width=True,
                ):
                    _save_prices(
                        [price for price in saved_prices if price.price_id != saved_price.price_id]
                    )
                    st.rerun()

            price_columns = st.columns(2)
            price_columns[0].metric(
                "Costo unitario",
                _format_money(saved_price.unit_cost, saved_price.currency),
            )
            price_columns[1].metric(
                "Precio de venta",
                _format_money(saved_price.unit_price, saved_price.currency),
            )

            render_info_card(
                "Base del precio",
                f"Material: {saved_price.material_label}. Equipo: {saved_price.asset_label}.",
                "REFERENCIA TEMPORAL",
            )
