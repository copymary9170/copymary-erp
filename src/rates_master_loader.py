"""Activa la fuente maestra de tasas sin reemplazar Configuración General."""
from __future__ import annotations

import streamlit as st

from src import app_shell
from src.rates_master import sync_official_rates_from_settings


def activate_rates_master() -> None:
    """Envuelve Configuración General para sincronizar su tasa oficial con Costeo.

    No sustituye el renderer ni borra historial. La sincronización ocurre al
    volver a renderizar la pantalla después de guardar la configuración.
    """
    original = app_shell.FUNCTIONAL_MODULES.get("Configuración General")
    if original is None or getattr(original, "_copymary_rates_master", False):
        return

    def wrapped() -> None:
        original()
        settings = st.session_state.get("general_settings")
        if settings is not None:
            sync_official_rates_from_settings(settings)

    wrapped._copymary_rates_master = True  # type: ignore[attr-defined]
    app_shell.FUNCTIONAL_MODULES["Configuración General"] = wrapped
