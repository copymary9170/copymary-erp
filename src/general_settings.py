"""Pantalla funcional temporal para la configuración general de CopyMary ERP."""

from dataclasses import dataclass

import streamlit as st

from src.components import render_info_card, render_page_header


@dataclass(frozen=True)
class GeneralSettings:
    business_name: str
    currency: str
    profit_margin: float
    monthly_internet: float
    monthly_electricity: float
    estimated_monthly_units: int

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
    other_cost: float
    quantity: int
    unit_cost: float
    total_cost: float
    unit_price: float
    total_price: float
    estimated_profit: float


def _format_money(value: float, currency: str) -> str:
    symbols = {"USD": "$", "VES": "Bs", "EUR": "€"}
    symbol = symbols.get(currency, currency)
    return f"{symbol} {value:,.2f}"


def _calculate_price_estimate(
    paper_cost: float,
    ink_cost: float,
    labor_cost: float,
    indirect_cost: float,
    other_cost: float,
    quantity: int,
    settings: GeneralSettings,
) -> PriceEstimate:
    unit_cost = paper_cost + ink_cost + labor_cost + indirect_cost + other_cost
    total_cost = unit_cost * quantity
    unit_price = unit_cost * settings.sale_multiplier
    total_price = unit_price * quantity
    return PriceEstimate(
        paper_cost=paper_cost,
        ink_cost=ink_cost,
        labor_cost=labor_cost,
        indirect_cost=indirect_cost,
        other_cost=other_cost,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        unit_price=unit_price,
        total_price=total_price,
        estimated_profit=total_price - total_cost,
    )


def render_general_settings() -> None:
    """Renderiza configuración y costeo temporal sin persistencia permanente."""
    with st.container(border=True):
        render_page_header(
            "Configuración General",
            "Define parámetros básicos y calcula precios orientativos para el negocio.",
        )
        st.caption("Los valores se conservan únicamente mientras esta sesión permanezca abierta.")

    st.warning(
        "Esta función no utiliza base de datos. Al cerrar o reiniciar la aplicación, "
        "la configuración y los cálculos pueden perderse."
    )

    default_settings = GeneralSettings(
        business_name="Copy Mary",
        currency="USD",
        profit_margin=40.0,
        monthly_internet=25.0,
        monthly_electricity=4.0,
        estimated_monthly_units=400,
    )
    stored_settings = st.session_state.get("general_settings")
    defaults = stored_settings if isinstance(stored_settings, GeneralSettings) else default_settings

    st.subheader("Datos del negocio")
    with st.form("general_settings_form"):
        business_name = st.text_input(
            "Nombre del negocio",
            value=defaults.business_name,
            max_chars=80,
        )
        currency = st.selectbox(
            "Moneda principal",
            options=("USD", "VES", "EUR"),
            index=("USD", "VES", "EUR").index(defaults.currency),
        )
        profit_margin = st.number_input(
            "Margen de ganancia (%)",
            min_value=0.0,
            max_value=500.0,
            value=float(defaults.profit_margin),
            step=1.0,
        )

        cost_columns = st.columns(3)
        with cost_columns[0]:
            monthly_internet = st.number_input(
                "Internet mensual",
                min_value=0.0,
                value=float(defaults.monthly_internet),
                step=1.0,
            )
        with cost_columns[1]:
            monthly_electricity = st.number_input(
                "Electricidad mensual",
                min_value=0.0,
                value=float(defaults.monthly_electricity),
                step=1.0,
            )
        with cost_columns[2]:
            estimated_monthly_units = st.number_input(
                "Producción mensual estimada",
                min_value=1,
                value=int(defaults.estimated_monthly_units),
                step=1,
                help="Cantidad aproximada de unidades, hojas o trabajos producidos al mes.",
            )

        submitted = st.form_submit_button(
            "Aplicar configuración",
            type="primary",
            use_container_width=True,
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
            )
            st.session_state.pop("price_estimate", None)
            st.success("Configuración aplicada durante esta sesión.")

    settings = st.session_state.get("general_settings", defaults)

    st.divider()
    st.subheader("Resumen calculado")
    summary_columns = st.columns(4)
    summary_columns[0].metric("Negocio", settings.business_name)
    summary_columns[1].metric(
        "Costos fijos mensuales",
        _format_money(settings.monthly_fixed_costs, settings.currency),
    )
    summary_columns[2].metric(
        "Costo fijo por unidad",
        _format_money(settings.fixed_cost_per_unit, settings.currency),
    )
    summary_columns[3].metric(
        "Multiplicador de venta",
        f"× {settings.sale_multiplier:.2f}",
    )

    render_info_card(
        "Prorrateo automático de costos fijos",
        (
            f"Los costos mensuales de internet y electricidad se distribuyen entre "
            f"{settings.estimated_monthly_units} unidades estimadas. El resultado es "
            f"{_format_money(settings.fixed_cost_per_unit, settings.currency)} por unidad."
        ),
        "COSTO INDIRECTO SUGERIDO",
    )

    st.divider()
    st.subheader("Calculadora detallada de costos")
    st.caption("Suma los costos por unidad y aplica el margen configurado arriba.")

    with st.form("price_estimate_form"):
        first_row = st.columns(3)
        with first_row[0]:
            paper_cost = st.number_input(
                "Papel por unidad",
                min_value=0.0,
                value=0.00,
                step=0.01,
                format="%.2f",
            )
        with first_row[1]:
            ink_cost = st.number_input(
                "Tinta por unidad",
                min_value=0.0,
                value=0.00,
                step=0.01,
                format="%.2f",
            )
        with first_row[2]:
            labor_cost = st.number_input(
                "Mano de obra por unidad",
                min_value=0.0,
                value=0.00,
                step=0.01,
                format="%.2f",
            )

        second_row = st.columns(3)
        with second_row[0]:
            indirect_cost = st.number_input(
                "Gastos indirectos por unidad",
                min_value=0.0,
                value=float(settings.fixed_cost_per_unit),
                step=0.01,
                format="%.2f",
                help="Se completa con el costo fijo por unidad calculado arriba; puedes modificarlo.",
            )
        with second_row[1]:
            other_cost = st.number_input(
                "Otros costos por unidad",
                min_value=0.0,
                value=0.00,
                step=0.01,
                format="%.2f",
            )
        with second_row[2]:
            quantity = st.number_input(
                "Cantidad",
                min_value=1,
                value=1,
                step=1,
            )

        calculate_submitted = st.form_submit_button(
            "Calcular precio detallado",
            type="primary",
            use_container_width=True,
        )

    if calculate_submitted:
        st.session_state.price_estimate = _calculate_price_estimate(
            paper_cost=float(paper_cost),
            ink_cost=float(ink_cost),
            labor_cost=float(labor_cost),
            indirect_cost=float(indirect_cost),
            other_cost=float(other_cost),
            quantity=int(quantity),
            settings=settings,
        )

    estimate = st.session_state.get("price_estimate")
    if estimate is not None:
        st.subheader("Resultado")
        result_columns = st.columns(4)
        result_columns[0].metric(
            "Costo por unidad",
            _format_money(estimate.unit_cost, settings.currency),
        )
        result_columns[1].metric(
            "Precio por unidad",
            _format_money(estimate.unit_price, settings.currency),
        )
        result_columns[2].metric(
            "Venta total",
            _format_money(estimate.total_price, settings.currency),
        )
        result_columns[3].metric(
            "Ganancia estimada",
            _format_money(estimate.estimated_profit, settings.currency),
        )

        breakdown_columns = st.columns(2)
        with breakdown_columns[0]:
            render_info_card(
                "Desglose por unidad",
                (
                    f"Papel: {_format_money(estimate.paper_cost, settings.currency)} · "
                    f"Tinta: {_format_money(estimate.ink_cost, settings.currency)} · "
                    f"Mano de obra: {_format_money(estimate.labor_cost, settings.currency)}"
                ),
                "COSTOS DIRECTOS",
            )
        with breakdown_columns[1]:
            render_info_card(
                "Otros componentes",
                (
                    f"Indirectos: {_format_money(estimate.indirect_cost, settings.currency)} · "
                    f"Otros: {_format_money(estimate.other_cost, settings.currency)} · "
                    f"Costo total: {_format_money(estimate.total_cost, settings.currency)}"
                ),
                "COSTOS COMPLEMENTARIOS",
            )

        render_info_card(
            "Resultado de la estimación",
            (
                f"Para {estimate.quantity} unidad(es), la venta orientativa total es "
                f"{_format_money(estimate.total_price, settings.currency)} y la ganancia estimada es "
                f"{_format_money(estimate.estimated_profit, settings.currency)}."
            ),
            "RESULTADO TEMPORAL",
        )

    st.info(
        "El resultado depende de los costos introducidos. Esta etapa todavía no obtiene datos "
        "automáticamente desde inventario, activos, nómina o contabilidad."
    )
