"""Restaura la franja compacta de tasas en todas las pantallas operativas.

La navegación activa termina delegando en ``app_shell.run_app``. Por eso la
franja debe envolver los renderers que ese shell ejecuta, después de que todos
los loaders hayan registrado o sustituido sus módulos.
"""
from __future__ import annotations

from functools import wraps
from typing import Callable

import streamlit as st

from src import app_shell
from src.payment_fees import rates_badge_html

_INSTALLED = False


def _render_rates_bar() -> None:
    html = rates_badge_html()
    if html:
        st.markdown(html, unsafe_allow_html=True)


def _wrap_renderer(renderer: Callable[[], None]) -> Callable[[], None]:
    if getattr(renderer, "_copymary_rates_bar", False):
        return renderer

    @wraps(renderer)
    def wrapped() -> None:
        _render_rates_bar()
        renderer()

    wrapped._copymary_rates_bar = True  # type: ignore[attr-defined]
    return wrapped


def activate_global_rates_bar() -> None:
    """Muestra las tasas en Inicio y módulos, excepto Configuración General."""
    global _INSTALLED
    if _INSTALLED:
        return

    app_shell.render_home = _wrap_renderer(app_shell.render_home)
    for page_name, renderer in tuple(app_shell.FUNCTIONAL_MODULES.items()):
        if page_name == "Configuración General":
            continue
        app_shell.FUNCTIONAL_MODULES[page_name] = _wrap_renderer(renderer)

    _INSTALLED = True
