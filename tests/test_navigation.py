"""Pruebas del helper de navegación `app_shell.go_to`."""

from __future__ import annotations

import pytest
import streamlit as st

from src import app_shell, module_bootstrap


@pytest.fixture(autouse=True)
def _bootstrap():
    """`go_to` recorre `NAVIGATION_GROUPS`, que se llenan con
    `activate_module_bootstrap()`. Sin esto los grupos base vienen vacíos y
    no se puede resolver la página."""
    module_bootstrap.activate_module_bootstrap()
    yield


def test_go_to_finds_page_in_inicio_group():
    """go_to() debe poder llegar a una página del grupo Inicio (usado por el
    botón 'Abrir' de la página de Novedades)."""
    try:
        app_shell.go_to("Venta rápida de mostrador")
    except st.errors.StreamlitAPIException:
        # st.rerun() lanza esta excepción fuera de un runtime real, es esperado.
        pass
    except Exception as exc:
        pytest.fail(f"go_to() falló para una página válida del grupo Inicio: {exc}")

    assert st.session_state.get("pending_navigation_area") == "Inicio"
    assert st.session_state.get("pending_navigation_page") == "Venta rápida de mostrador"


def test_go_to_finds_page_in_administracion_group():
    """Igual, pero para una página de otro grupo — verifica que la búsqueda
    no depende de un grupo específico."""
    try:
        app_shell.go_to("RRHH y nómina")
    except (st.errors.StreamlitAPIException, Exception):
        pass

    assert st.session_state.get("pending_navigation_area") == "Administración"
    assert st.session_state.get("pending_navigation_page") == "RRHH y nómina"


def test_go_to_reports_error_for_unknown_page():
    """Si la página no existe, no debe lanzar excepción cruda ni cambiar el
    estado de navegación (solo mostrar un error de Streamlit)."""
    st.session_state.pop("pending_navigation_area", None)
    st.session_state.pop("pending_navigation_page", None)

    app_shell.go_to("Página inexistente XYZ")

    assert "pending_navigation_area" not in st.session_state
    assert "pending_navigation_page" not in st.session_state
