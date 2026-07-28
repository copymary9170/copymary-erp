"""Pruebas del helper de navegación `app_shell.go_to`."""

from __future__ import annotations

import pytest
import streamlit as st

from src import app_shell, module_bootstrap


@pytest.fixture(autouse=True)
def _bootstrap():
    """Carga renderers sin alterar la taxonomía canónica."""
    module_bootstrap.activate_module_bootstrap()
    yield


def _call_go_to(page: str) -> None:
    try:
        app_shell.go_to(page)
    except st.errors.StreamlitAPIException:
        # st.rerun() lanza esta excepción fuera de un runtime real, es esperado.
        pass


def test_go_to_resolves_quick_sale_to_commercial_area():
    _call_go_to("Venta rápida de mostrador")

    assert st.session_state.get("pending_navigation_area") == "Comercial y CRM"
    assert st.session_state.get("pending_navigation_page") == "Venta rápida de mostrador"


def test_go_to_resolves_payroll_to_talent_area():
    _call_go_to("RRHH y nómina")

    assert st.session_state.get("pending_navigation_area") == "Talento humano"
    assert st.session_state.get("pending_navigation_page") == "RRHH y nómina"


def test_bootstrap_does_not_create_legacy_navigation_groups():
    groups = app_shell.navigation_groups()

    assert "Productos e inventario" not in groups
    assert "Administración" not in groups
    assert "Venta rápida de mostrador" not in groups["Inicio"]
    assert "Venta rápida de mostrador" in groups["Comercial y CRM"]


def test_go_to_reports_error_for_unknown_page():
    st.session_state.pop("pending_navigation_area", None)
    st.session_state.pop("pending_navigation_page", None)

    app_shell.go_to("Página inexistente XYZ")

    assert "pending_navigation_area" not in st.session_state
    assert "pending_navigation_page" not in st.session_state
