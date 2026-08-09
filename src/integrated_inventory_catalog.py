"""Integra el Catálogo de artículos dentro del módulo Inventario."""

from __future__ import annotations

import streamlit as st

from src.catalog_items import render_catalog_items
from src.printable_materials import activate_printing_filters


activate_printing_filters()


def wrap_inventory_renderer(base_renderer):
    """Devuelve un renderer único con Inventario y Catálogo como secciones internas."""

    def render_inventory_integrated() -> None:
        inventory_tab, catalog_tab = st.tabs(("Existencias y control", "Catálogo de artículos"))
        with inventory_tab:
            base_renderer()
        with catalog_tab:
            # Única fuente de verdad: la misma interfaz completa del catálogo maestro
            # se usa tanto aquí como en cualquier acceso directo al catálogo.
            render_catalog_items()

    return render_inventory_integrated
