"""Ajuste temporal de precios guardados mediante redondeo comercial."""

import math

import streamlit as st

from src.components import render_info_card, render_page_header


ROUNDING_OPTIONS = {
    "Sin redondeo": 0.0,
    "Al siguiente 0,05": 0.05,
    "Al siguiente 0,10": 0.10,
    "Al siguiente 0,25": 0.25,
    "Al siguiente 0,50": 0.50,
    "Al siguiente 1,00": 1.00,
}


def _get_saved_prices() -> list[dict]:
    raw_prices = st.session_state.get("saved_prices", [])
    prices: list[dict] = []
    for raw_price in raw_prices:
        if isinstance(raw_price, dict):
            prices.append(dict(raw_price))
        else:
            prices.append(
                {
                    "price_id": getattr(raw_price, "price_id", ""),
                    "name": getattr(raw_price, "name", "Producto o servicio"),
                    "material_label": getattr(raw_price, "material_label", "Costo manual"),
                    "asset_label": getattr(raw_price, "asset_label", "Sin equipo registrado"),
                    "currency": getattr(raw_price, "currency", "USD"),
                    "profit_margin": float(getattr(raw_price, "profit_margin", 0.0)),
                    "unit_cost": float(getattr(raw_price, "unit_cost", 0.0)),
                    "unit_price": float(getattr(raw_price, "unit_price", 0.0)),
                }
            )
    return prices


def _round_up(value: float, increment: float) -> float:
    if increment <= 0:
        return value
    return math.ceil((value - 1e-12) / increment) * increment


def _format_money(value: float, currency: str) -> str:
    symbols = {"USD": "$", "VES": "Bs", "EUR": "€"}
    symbol = symbols.get(currency, currency)
    return f"{symbol} {value:,.2f}"


def render_price_rounding() -> None:
    """Renderiza el redondeo comercial de precios guardados."""
    with st.container(border=True):
        render_page_header(
            "Ajustar precios",
            "Redondea hacia arriba los precios guardados para obtener importes comerciales más cómodos.",
        )
        st.caption("Los cambios se aplican únicamente a la lista temporal de esta sesión.")

    prices = _get_saved_prices()
    if not prices:
        st.info("No hay precios guardados. Primero calcula y guarda precios desde Costeo.")
        return

    rounding_label = st.selectbox(
        "Regla de redondeo",
        tuple(ROUNDING_OPTIONS.keys()),
        index=2,
        help="El precio siempre se redondea hacia arriba para no reducir la ganancia calculada.",
    )
    increment = ROUNDING_OPTIONS[rounding_label]

    st.subheader("Vista previa")
    adjusted_prices: list[dict] = []
    total_increase = 0.0

    for price in prices:
        current_price = float(price.get("unit_price", 0.0))
        rounded_price = _round_up(current_price, increment)
        increase = rounded_price - current_price
        total_increase += increase

        adjusted_price = dict(price)
        adjusted_price["unit_price"] = rounded_price
        adjusted_prices.append(adjusted_price)

        with st.container(border=True):
            st.markdown(f"### {price.get('name', 'Producto o servicio')}")
            metric_columns = st.columns(3)
            metric_columns[0].metric(
                "Precio calculado",
                _format_money(current_price, str(price.get("currency", "USD"))),
            )
            metric_columns[1].metric(
                "Precio redondeado",
                _format_money(rounded_price, str(price.get("currency", "USD"))),
            )
            metric_columns[2].metric(
                "Ajuste",
                _format_money(increase, str(price.get("currency", "USD"))),
            )

    render_info_card(
        "Protección del margen",
        (
            "El redondeo se realiza siempre hacia arriba. Así el precio final nunca queda por debajo "
            "del valor calculado originalmente."
        ),
        "REGLA COMERCIAL",
    )

    if increment <= 0:
        st.info("Seleccionaste Sin redondeo. No hay cambios que aplicar.")
        return

    if st.button(
        "Aplicar redondeo a la lista temporal",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.saved_prices = adjusted_prices
        st.success(
            f"Se aplicó {rounding_label.lower()} a {len(adjusted_prices)} precio(s) guardado(s)."
        )
        st.rerun()

    st.caption(
        f"Ajuste acumulado estimado sobre todos los precios mostrados: {total_increase:,.2f}."
    )
