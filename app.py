"""Punto de entrada de CopyMary ERP."""

import streamlit as st

from src.assets import render_assets
from src.components import apply_base_styles, render_info_card, render_page_header
from src.config import APP_NAME, APP_VERSION, PROJECT_STATUS
from src.costing import render_costing
from src.general_settings import render_general_settings
from src.inventory import render_inventory
from src.modules import MODULES
from src.price_export import render_price_export
from src.price_rounding import render_price_rounding

st.set_page_config(
    page_title=APP_NAME,
    page_icon="CM",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_base_styles()

FUNCTIONAL_MODULES = {
    "Configuración General": render_general_settings,
    "Activos": render_assets,
    "Inventario": render_inventory,
    "Costeo": render_costing,
    "Ajustar precios": render_price_rounding,
    "Exportar precios": render_price_export,
}
NAVIGATION_OPTIONS = ["Inicio", *MODULES.keys()]
if "Inventario" not in NAVIGATION_OPTIONS:
    NAVIGATION_OPTIONS.insert(-1, "Inventario")
if "Ajustar precios" not in NAVIGATION_OPTIONS:
    NAVIGATION_OPTIONS.append("Ajustar precios")
if "Exportar precios" not in NAVIGATION_OPTIONS:
    NAVIGATION_OPTIONS.append("Exportar precios")

with st.sidebar:
    st.title(APP_NAME)
    st.caption("Panel empresarial en construcción")
    st.divider()
    selected_page = st.radio(
        "Secciones disponibles",
        NAVIGATION_OPTIONS,
        label_visibility="collapsed",
    )
    st.divider()
    st.caption(f"Versión {APP_VERSION}")
    st.caption(f"Estado: {PROJECT_STATUS}")
    st.info("Las funciones actuales trabajan solo durante la sesión y no guardan datos permanentemente.")


def render_home() -> None:
    with st.container(border=True):
        render_page_header(
            APP_NAME,
            "Sistema empresarial en construcción con módulos temporales conectados.",
        )
        st.caption("Configuración, activos, inventario y costeo funcionan durante la sesión actual.")

    st.warning("Los datos pueden perderse al cerrar o reiniciar la aplicación.")

    st.subheader("Flujo funcional actual")
    flow_columns = st.columns(3)
    flow = (
        ("Configuración General", "Define moneda, margen y costos fijos."),
        ("Activos", "Aporta la depreciación por unidad del equipo."),
        ("Inventario", "Calcula el costo unitario de los materiales."),
        ("Costeo", "Combina los datos y calcula precios orientativos."),
        ("Ajustar precios", "Redondea hacia arriba para proteger el margen."),
        ("Exportar precios", "Descarga en CSV la lista guardada durante la sesión."),
    )
    for index, (title, description) in enumerate(flow):
        with flow_columns[index % 3]:
            render_info_card(title, description, "FUNCIÓN TEMPORAL")

    st.divider()
    st.subheader("Estado de los demás módulos")
    descriptive_modules = [
        (name, info)
        for name, info in MODULES.items()
        if name not in FUNCTIONAL_MODULES
    ]
    module_columns = st.columns(2)
    for index, (name, info) in enumerate(descriptive_modules):
        with module_columns[index % 2]:
            render_info_card(name, info["description"], "INTERFAZ DESCRIPTIVA")


def render_descriptive_module(module_name: str) -> None:
    module_info = MODULES.get(module_name)
    if module_info is None:
        st.error("La sección solicitada no está disponible.")
        return

    with st.container(border=True):
        render_page_header(module_name, module_info["description"])
        st.caption("Este módulo permanece en etapa de Blueprint.")

    st.warning("Esta pantalla todavía no ejecuta operaciones ni guarda datos.")
    render_info_card("Estado", module_info["status"], "SITUACIÓN ACTUAL")
    render_info_card("Objetivo", module_info["objective"], "PROPÓSITO")
    st.subheader("Funciones previstas")
    for planned_function in module_info["planned_functions"]:
        st.markdown(f"- {planned_function}")


if selected_page == "Inicio":
    render_home()
elif selected_page in FUNCTIONAL_MODULES:
    FUNCTIONAL_MODULES[selected_page]()
elif selected_page in MODULES:
    render_descriptive_module(selected_page)
else:
    st.error("La opción seleccionada no existe.")
