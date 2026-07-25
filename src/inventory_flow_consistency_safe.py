"""Consistencia visual del flujo Catálogo → Compras → Recepción → Inventario."""
from __future__ import annotations

from collections.abc import Callable

import streamlit as st

_BASE_RENDERER: Callable[[], None] | None = None


def configure_base_renderer(renderer: Callable[[], None]) -> None:
    """Conserva la pantalla ya activada para envolverla sin reemplazar su lógica."""
    global _BASE_RENDERER
    _BASE_RENDERER = renderer


def _render_flow_guide() -> None:
    st.markdown("#### Flujo operativo")
    cols = st.columns(4)
    steps = (
        ("1. Catálogo", "Define el artículo y sus datos técnicos. No aumenta existencias."),
        ("2. Compras", "Registra la orden, proveedor, precios y condiciones de compra."),
        ("3. Recepción", "Confirma lo recibido y genera la entrada real al inventario."),
        ("4. Inventario", "Controla existencias, reservas, movimientos, conteos y reposición."),
    )
    for column, (title, description) in zip(cols, steps):
        with column:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(description)

    st.caption(
        "Términos unificados: existencia física = cantidad registrada; reservado = cantidad apartada; "
        "disponible = existencia física menos reservas activas; pendiente de recibir = compra aún no confirmada."
    )


def render_inventory_with_consistent_flow() -> None:
    """Añade una guía común y conserva intacta la pantalla operativa de Inventario."""
    _render_flow_guide()
    st.divider()
    if _BASE_RENDERER is None:
        st.error("No se pudo cargar la pantalla base de Inventario.")
        return
    _BASE_RENDERER()
