"""Mantiene visible la franja compacta de tasas en las pantallas operativas.

Streamlit vuelve a ejecutar ``app.py`` en cada interacción, mientras los módulos
importados permanecen en memoria. Los loaders pueden sustituir renderers en cada
rerun; por eso esta integración debe revisar y envolver los renderers actuales
cada vez que se activa, en lugar de depender de una bandera global de una sola
instalación.
"""
from __future__ import annotations

from functools import wraps
from typing import Callable

import streamlit as st

from src import app_shell
from src.payment_fees import rates_badge_html


def _render_rates_bar() -> None:
    html = rates_badge_html()
    if html:
        st.markdown(html, unsafe_allow_html=True)


def _wrap_renderer(renderer: Callable[[], None]) -> Callable[[], None]:
    """Envuelve un renderer una sola vez, incluso tras varios reruns."""
    if getattr(renderer, "_copymary_rates_bar", False):
        return renderer

    @wraps(renderer)
    def wrapped() -> None:
        _render_rates_bar()
        renderer()

    wrapped._copymary_rates_bar = True  # type: ignore[attr-defined]
    return wrapped


def activate_global_rates_bar() -> None:
    """Reaplica la barra a los renderers vigentes en cada rerun de Streamlit.

    Los loaders ejecutados antes de esta función pueden reemplazar funciones del
    diccionario ``FUNCTIONAL_MODULES``. Se recorren siempre los valores actuales;
    ``_wrap_renderer`` evita envolver dos veces los que ya conservan la barra.
    Configuración General queda excluida porque muestra el detalle completo.
    """
    app_shell.render_home = _wrap_renderer(app_shell.render_home)
    for page_name, renderer in tuple(app_shell.FUNCTIONAL_MODULES.items()):
        if page_name == "Configuración General":
            continue
        app_shell.FUNCTIONAL_MODULES[page_name] = _wrap_renderer(renderer)
