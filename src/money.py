"""Utilidades compartidas de moneda para CopyMary ERP."""

import streamlit as st


CURRENCY_SYMBOLS = {"USD": "$", "VES": "Bs", "EUR": "€"}


def get_currency() -> str:
    """Devuelve la moneda configurada o USD si aún no existe configuración."""
    settings = st.session_state.get("general_settings")
    if settings is None:
        return "USD"

    if isinstance(settings, dict):
        currency = settings.get("currency", "USD")
    else:
        currency = getattr(settings, "currency", "USD")

    resolved_currency = str(currency).upper()
    return resolved_currency if resolved_currency in CURRENCY_SYMBOLS else "USD"


def format_money(value: float, currency: str | None = None) -> str:
    """Formatea un importe con la moneda principal de la sesión."""
    resolved_currency = currency or get_currency()
    symbol = CURRENCY_SYMBOLS.get(resolved_currency, resolved_currency)
    return f"{symbol} {value:,.2f}"
