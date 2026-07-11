"""Pruebas de utilidades de moneda (`src/money.py`)."""

from __future__ import annotations

import streamlit as st

from src import money


def test_get_currency_defaults_to_usd_without_settings():
    assert money.get_currency() == "USD"


def test_get_currency_reads_from_dict_settings():
    st.session_state["general_settings"] = {"currency": "ves"}
    assert money.get_currency() == "VES"


def test_get_currency_falls_back_to_usd_for_unknown_currency():
    st.session_state["general_settings"] = {"currency": "XYZ"}
    assert money.get_currency() == "USD"


def test_format_money_uses_symbol_and_two_decimals():
    assert money.format_money(1234.5, currency="USD") == "$ 1,234.50"


def test_format_money_uses_ves_symbol():
    assert money.format_money(100, currency="VES") == "Bs 100.00"


def test_format_money_uses_session_currency_when_not_specified():
    st.session_state["general_settings"] = {"currency": "EUR"}
    assert money.format_money(50) == "€ 50.00"
