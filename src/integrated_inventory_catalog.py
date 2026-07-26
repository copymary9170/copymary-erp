"""Integra el Catálogo de artículos dentro del módulo Inventario."""

from __future__ import annotations

import streamlit as st

from src.catalog_items_reactive import render_catalog_items


def wrap_inventory_renderer(base_renderer):
    """Devuelve un renderer único con Inventario y Catálogo como secciones internas."""

    def render_inventory_integrated() -> None:
        inventory_tab, catalog_tab = st.tabs(("Existencias y control", "Catálogo de artículos"))
        with inventory_tab:
            base_renderer()
        with catalog_tab:
            render_catalog_items()

    return render_inventory_integrated
