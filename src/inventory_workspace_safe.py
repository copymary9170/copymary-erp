"""Espacio de trabajo de Inventario sin registrar compras dentro del módulo.

Conserva las funciones operativas ya activadas y elimina de la navegación de
Inventario las pestañas heredadas de Registrar y Factura de compra.
"""
from __future__ import annotations

import streamlit as st

from src import inventory_enterprise


def render_inventory_workspace_safe() -> None:
    """Muestra únicamente las responsabilidades propias de Inventario."""
    inventory_enterprise.render_page_header(
        "Inventario empresarial",
        "Consulta existencias, movimientos, reservas, conteos, lotes y reposición. "
        "Las compras se gestionan en Compras y la mercancía se incorpora desde Recepción.",
    )
    rows = inventory_enterprise._items()

    st.info(
        "Separación operativa activa: los artículos se crean desde Catálogo, las compras "
        "se registran en Compras y las entradas compradas llegan al inventario únicamente "
        "al confirmar su recepción."
    )

    tabs = st.tabs((
        "Panel",
        "Existencias",
        "Movimientos",
        "Reservas",
        "Conteo físico",
        "Reposición",
    ))
    with tabs[0]:
        inventory_enterprise._dashboard(rows)
    with tabs[1]:
        inventory_enterprise._catalog(rows)
    with tabs[2]:
        inventory_enterprise._movements(rows)
    with tabs[3]:
        inventory_enterprise._reservations(rows)
    with tabs[4]:
        inventory_enterprise._counts(rows)
    with tabs[5]:
        inventory_enterprise._replenishment(rows)

    st.caption(
        "Inventario ya no registra artículos ni facturas de compra. Esta separación evita "
        "duplicar entradas, costos y documentos entre Catálogo, Compras, Recepción e Inventario."
    )
