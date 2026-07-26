"""Integra Recepción de mercancía dentro del módulo Compras."""

from __future__ import annotations

import streamlit as st

from src import purchases_plus


def wrap_purchases_renderer(base_renderer):
    """Devuelve un renderer único con gestión de compras y recepción interna."""

    def render_purchases_integrated() -> None:
        management_tab, receiving_tab = st.tabs(("Gestión de compras", "Recepción de mercancía"))
        with management_tab:
            base_renderer()
        with receiving_tab:
            purchases_plus.render_purchases_plus()

    return render_purchases_integrated
