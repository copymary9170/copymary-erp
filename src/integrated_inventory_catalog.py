"""Integra el Catálogo de artículos dentro del módulo Inventario."""

from __future__ import annotations

import streamlit as st

from src.catalog_items import get_catalog_items
from src.catalog_items_reactive import render_catalog_items
from src.printable_materials import activate_printing_filters, is_printable, set_printable


activate_printing_filters()


def _render_printable_settings() -> None:
    """Permite decidir qué artículos deben aparecer en Impresión."""
    items = get_catalog_items(include_inactive=False)
    if not items:
        return

    st.divider()
    with st.expander("Materiales disponibles en Impresión", expanded=False):
        st.caption(
            "Marca únicamente los artículos sobre los que realmente se puede imprimir. "
            "Los que desmarques seguirán disponibles en Inventario, Cameo, manualidades y otros procesos."
        )
        changed = False
        for item in items:
            key = f"catalog_printable_{item.item_id}"
            current = is_printable(item)
            selected = st.checkbox(
                f"{item.name} · {item.sku or 'Sin SKU'}",
                value=current,
                key=key,
                help="Al desmarcarlo dejará de aparecer en los selectores del apartado de impresión.",
            )
            if selected != current:
                set_printable(item, selected)
                changed = True
        if changed:
            st.success("La lista de materiales de impresión fue actualizada.")
            st.rerun()


def wrap_inventory_renderer(base_renderer):
    """Devuelve un renderer único con Inventario y Catálogo como secciones internas."""

    def render_inventory_integrated() -> None:
        inventory_tab, catalog_tab = st.tabs(("Existencias y control", "Catálogo de artículos"))
        with inventory_tab:
            base_renderer()
        with catalog_tab:
            render_catalog_items()
            _render_printable_settings()

    return render_inventory_integrated
