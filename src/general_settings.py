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

    @property
    def monthly_fixed_costs(self) -> float:
        return self.monthly_internet + self.monthly_electricity

    @property
    def sale_multiplier(self) -> float:
        return 1 + (self.profit_margin / 100)


def _format_money(value: float, currency: str) -> str:
    symbols = {"USD": "$", "VES": "Bs", "EUR": "€"}
    symbol = symbols.get(currency, currency)
    return f"{symbol} {value:,.2f}"


def render_general_settings() -> None:
    """Renderiza un formulario funcional sin persistencia permanente."""
    with st.container(border=True):
        render_page_header(
            "Configuración General",
            "Define parámetros básicos para realizar cálculos iniciales dentro del sistema.",
        )
        st.caption("Los valores se conservan únicamente mientras esta sesión permanezca abierta.")

    st.warning(
        "Esta primera función no utiliza base de datos. Al cerrar o reiniciar la aplicación, "
        "la configuración puede perderse."
    )

    defaults = st.session_state.get(
        "general_settings",
        GeneralSettings(
            business_name="Copy Mary",
            currency="USD",
            profit_margin=40.0,
            monthly_internet=25.0,
            monthly_electricity=4.0,
        ),
    )

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

        cost_columns = st.columns(2)
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
            )
            st.success("Configuración aplicada durante esta sesión.")

    settings = st.session_state.get("general_settings", defaults)

    st.divider()
    st.subheader("Resumen calculado")
    summary_columns = st.columns(3)
    summary_columns[0].metric("Negocio", settings.business_name)
    summary_columns[1].metric(
        "Costos fijos mensuales",
        _format_money(settings.monthly_fixed_costs, settings.currency),
    )
    summary_columns[2].metric(
        "Multiplicador de venta",
        f"× {settings.sale_multiplier:.2f}",
    )

    render_info_card(
        "Cómo se interpreta el multiplicador",
        (
            f"Con un margen de {settings.profit_margin:.0f}%, un costo base de "
            f"{_format_money(10, settings.currency)} produciría un precio orientativo de "
            f"{_format_money(10 * settings.sale_multiplier, settings.currency)}."
        ),
        "CÁLCULO DE REFERENCIA",
    )

    st.info(
        "Este cálculo es orientativo. Todavía no incluye tinta, papel, mano de obra, "
        "depreciación, comisiones ni otros costos del negocio."
    )
