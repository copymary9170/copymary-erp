"""Configuración general y calculadora orientativa de costos."""

from dataclasses import dataclass

import streamlit as st

from src.assets import Asset, _get_assets
from src.components import render_info_card, render_page_header


@dataclass(frozen=True)
class GeneralSettings:
    business_name: str
    currency: str
    profit_margin: float
    monthly_internet: float
    monthly_electricity: float
    estimated_monthly_units: int
    selected_asset_ids: tuple[str, ...]

    @property
    def monthly_fixed_costs(self) -> float:
        return self.monthly_internet + self.monthly_electricity

    @property
    def fixed_cost_per_unit(self) -> float:
        return self.monthly_fixed_costs / self.estimated_monthly_units

    @property
    def sale_multiplier(self) -> float:
        return 1 + (self.profit_margin / 100)


@dataclass(frozen=True)
class PriceEstimate:
    paper_cost: float
    ink_cost: float
    labor_cost: float
    indirect_cost: float
    equipment_cost: float
    other_cost: float
    quantity: int
    unit_cost: float
    total_cost: float
    unit_price: float
    total_price: float
    estimated_profit: float


def _format_money(value: float, currency: str) -> str:
    symbols = {"USD": "$", "VES": "Bs", "EUR": "€"}
    return f"{symbols.get(currency, currency)} {value:,.2f}"


def _selected_assets(settings: GeneralSettings, assets: list[Asset]) -> list[Asset]:
    selected_ids = set(settings.selected_asset_ids)
    return [asset for asset in assets if asset.asset_id in selected_ids]


def _equipment_cost_per_unit(settings: GeneralSettings, assets: list[Asset]) -> float:
    return sum(asset.depreciation_per_unit for asset in _selected_assets(settings, assets))


def _calculate_price_estimate(
    paper_cost: float,
    ink_cost: float,
    labor_cost: float,
    indirect_cost: float,
    equipment_cost: float,
    other_cost: float,
    quantity: int,
    settings: GeneralSettings,
) -> PriceEstimate:
    unit_cost = paper_cost + ink_cost + labor_cost + indirect_cost + equipment_cost + other_cost
    total_cost = unit_cost * quantity
    unit_price = unit_cost * settings.sale_multiplier
    total_price = unit_price * quantity
    return PriceEstimate(
        paper_cost=paper_cost,
        ink_cost=ink_cost,
        labor_cost=labor_cost,
        indirect_cost=indirect_cost,
        equipment_cost=equipment_cost,
        other_cost=other_cost,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        unit_price=unit_price,
        total_price=total_price,
        estimated_profit=total_price - total_cost,
    )


def render_general_settings() -> None:
    """Renderiza la configuración y obtiene los equipos desde Activos."""
    with st.container(border=True):
        render_page_header(
            "Configuración General",
            "Define parámetros básicos y calcula precios orientativos para el negocio.",
        )
        st.caption("Los valores se conservan únicamente mientras esta sesión permanezca abierta.")

    st.warning(
        "Esta función todavía no utiliza base de datos. Al cerrar o reiniciar la aplicación, "
        "la configuración y los cálculos pueden perderse."
    )

    assets = _get_assets()
    asset_options = {asset.asset_id: asset for asset in assets}
    default_asset_ids = tuple(asset_options)
    default_settings = GeneralSettings(
        business_name="Copy Mary",
        currency="USD",
        profit_margin=40.0,
        monthly_internet=5.0,
        monthly_electricity=3.0,
        estimated_monthly_units=200,
        selected_asset_ids=default_asset_ids,
    )
    stored_settings = st.session_state.get("general_settings")
    defaults = stored_settings if isinstance(stored_settings, GeneralSettings) else default_settings
    valid_default_ids = [asset_id for asset_id in defaults.selected_asset_ids if asset_id in asset_options]

    st.subheader("Datos del negocio")
    with st.form("general_settings_form"):
        business_name = st.text_input("Nombre del negocio", value=defaults.business_name, max_chars=80)
        currency = st.selectbox(
            "Moneda principal",
            options=("USD", "VES", "EUR"),
            index=("USD", "VES", "EUR").index(defaults.currency),
        )
        profit_margin = st.number_input(
            "Margen de ganancia (%)", min_value=0.0, max_value=500.0,
            value=float(defaults.profit_margin), step=1.0,
        )

        cost_columns = st.columns(3)
        with cost_columns[0]:
            monthly_internet = st.number_input(
                "Internet mensual", min_value=0.0,
                value=float(defaults.monthly_internet), step=1.0,
            )
        with cost_columns[1]:
            monthly_electricity = st.number_input(
                "Electricidad mensual", min_value=0.0,
                value=float(defaults.monthly_electricity), step=1.0,
            )
        with cost_columns[2]:
            estimated_monthly_units = st.number_input(
                "Producción mensual estimada", min_value=1,
                value=int(defaults.estimated_monthly_units), step=1,
                help="Cantidad aproximada de unidades, hojas o trabajos producidos al mes.",
            )

        st.markdown("#### Equipos tomados desde Activos")
        if assets:
            selected_asset_ids = st.multiselect(
                "Activos productivos incluidos en el cálculo",
                options=list(asset_options),
                default=valid_default_ids,
                format_func=lambda asset_id: (
                    f"{asset_options[asset_id].name} · {asset_options[asset_id].category} · "
                    f"{_format_money(asset_options[asset_id].acquisition_cost, currency)} · "
                    f"{asset_options[asset_id].lifetime_units:,} unidades"
                ),
                help=(
                    "El nombre, costo de adquisición y vida útil se leen automáticamente del módulo Activos. "
                    "Modifica esos datos allí para actualizar este cálculo."
                ),
            )
            preview_cost = sum(asset_options[item].depreciation_per_unit for item in selected_asset_ids)
            st.caption(
                f"Depreciación combinada calculada automáticamente: "
                f"{_format_money(preview_cost, currency)} por unidad."
            )
        else:
            selected_asset_ids = []
            st.info(
                "No hay activos registrados. Ve a Activos, registra la impresora o equipo y luego vuelve aquí."
            )

        submitted = st.form_submit_button(
            "Guardar configuración", type="primary", use_container_width=True,
        )

    if submitted:
        cleaned_name = business_name.strip()
        if not cleaned_name:
            st.error("El nombre del negocio no puede quedar vacío.")
        else:
            st.session_state.general_settings = GeneralSettings(
                business_name=cleaned_name,
                currency=currency,
                profit_margin=float(profit_margin),
                monthly_internet=float(monthly_internet),
                monthly_electricity=float(monthly_electricity),
                estimated_monthly_units=int(estimated_monthly_units),
                selected_asset_ids=tuple(selected_asset_ids),
            )
            st.session_state.pop("price_estimate", None)
            st.success("Configuración guardada durante esta sesión.")
            st.rerun()

    settings = st.session_state.get("general_settings", defaults)
    selected_assets = _selected_assets(settings, assets)
    equipment_cost_per_unit = _equipment_cost_per_unit(settings, assets)

    st.divider()
    st.subheader("Resumen calculado")
    summary_columns = st.columns(4)
    summary_columns[0].metric("Negocio", settings.business_name)
    summary_columns[1].metric(
        "Costo fijo por unidad", _format_money(settings.fixed_cost_per_unit, settings.currency)
    )
    summary_columns[2].metric(
        "Depreciación por unidad", _format_money(equipment_cost_per_unit, settings.currency)
    )
    summary_columns[3].metric("Multiplicador de venta", f"× {settings.sale_multiplier:.2f}")

    cards = st.columns(2)
    with cards[0]:
        render_info_card(
            "Prorrateo de costos fijos",
            f"Internet y electricidad se distribuyen entre {settings.estimated_monthly_units:,} unidades. "
            f"El resultado es {_format_money(settings.fixed_cost_per_unit, settings.currency)} por unidad.",
            "COSTO INDIRECTO SUGERIDO",
        )
    with cards[1]:
        if selected_assets:
            names = ", ".join(asset.name for asset in selected_assets)
            detail = (
                f"Equipos incluidos: {names}. La depreciación se calcula con el costo y la vida útil "
                f"registrados en Activos: {_format_money(equipment_cost_per_unit, settings.currency)} por unidad."
            )
        else:
            detail = "No se ha seleccionado ningún activo productivo para el cálculo."
        render_info_card("Reserva para reemplazo de equipos", detail, "DEPRECIACIÓN AUTOMÁTICA")

    st.divider()
    st.subheader("Calculadora detallada de costos")
    st.caption("Suma los costos por unidad y aplica el margen configurado arriba.")

    with st.form("price_estimate_form"):
        first_row = st.columns(3)
        with first_row[0]:
            paper_cost = st.number_input("Papel por unidad", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        with first_row[1]:
            ink_cost = st.number_input("Tinta por unidad", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        with first_row[2]:
            labor_cost = st.number_input("Mano de obra por unidad", min_value=0.0, value=0.0, step=0.01, format="%.2f")

        second_row = st.columns(4)
        with second_row[0]:
            indirect_cost = st.number_input(
                "Gastos indirectos por unidad", min_value=0.0,
                value=float(settings.fixed_cost_per_unit), step=0.01, format="%.2f",
            )
        with second_row[1]:
            equipment_cost = st.number_input(
                "Depreciación de equipos por unidad", min_value=0.0,
                value=float(equipment_cost_per_unit), step=0.001, format="%.3f",
                help="Se obtiene automáticamente de los activos seleccionados.",
            )
        with second_row[2]:
            other_cost = st.number_input("Otros costos por unidad", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        with second_row[3]:
            quantity = st.number_input("Cantidad", min_value=1, value=1, step=1)

        calculate_submitted = st.form_submit_button(
            "Calcular precio detallado", type="primary", use_container_width=True,
        )

    if calculate_submitted:
        st.session_state.price_estimate = _calculate_price_estimate(
            paper_cost=float(paper_cost), ink_cost=float(ink_cost), labor_cost=float(labor_cost),
            indirect_cost=float(indirect_cost), equipment_cost=float(equipment_cost),
            other_cost=float(other_cost), quantity=int(quantity), settings=settings,
        )

    estimate = st.session_state.get("price_estimate")
    if estimate is not None:
        st.subheader("Resultado")
        result_columns = st.columns(4)
        result_columns[0].metric("Costo por unidad", _format_money(estimate.unit_cost, settings.currency))
        result_columns[1].metric("Precio por unidad", _format_money(estimate.unit_price, settings.currency))
        result_columns[2].metric("Venta total", _format_money(estimate.total_price, settings.currency))
        result_columns[3].metric("Ganancia estimada", _format_money(estimate.estimated_profit, settings.currency))

        render_info_card(
            "Resultado de la estimación",
            f"Para {estimate.quantity} unidad(es), el costo total es "
            f"{_format_money(estimate.total_cost, settings.currency)}, la venta orientativa es "
            f"{_format_money(estimate.total_price, settings.currency)} y la ganancia estimada es "
            f"{_format_money(estimate.estimated_profit, settings.currency)}.",
            "RESULTADO TEMPORAL",
        )

    st.info(
        "Los equipos ya no se escriben manualmente aquí. El nombre, costo y vida útil provienen del módulo Activos."
    )
