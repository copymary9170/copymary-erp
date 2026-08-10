"""Integra Recepción y Análisis de compras dentro del módulo Compras."""

from __future__ import annotations

import streamlit as st

from src import purchases_plus
from src.purchase_analysis import render_purchase_analysis


def wrap_purchases_renderer(base_renderer):
    """Devuelve un renderer único con gestión, recepción y análisis de compras."""

    def render_purchases_integrated() -> None:
        management_tab, receiving_tab, analysis_tab = st.tabs(
            ("Gestión de compras", "Recepción de mercancía", "Análisis de compras")
        )
        with management_tab:
            base_renderer()
        with receiving_tab:
            purchases_plus.render_purchases_plus()
        with analysis_tab:
            render_purchase_analysis()

    return render_purchases_integrated
