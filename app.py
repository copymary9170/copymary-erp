"""Punto de entrada de la primera interfaz funcional de CopyMary ERP."""

import streamlit as st

from src.components import (
    apply_base_styles,
    render_info_card,
    render_list_section,
    render_page_header,
)
from src.config import (
    APP_NAME,
    APP_VERSION,
    CREATED_BLUEPRINTS,
    PLANNED_MODULES,
    PROJECT_STATUS,
)
from src.general_settings import render_general_settings
from src.modules import MODULES


st.set_page_config(
    page_title=APP_NAME,
    page_icon="CM",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_base_styles()

NAVIGATION_OPTIONS = ["Inicio", *MODULES.keys()]

with st.sidebar:
    st.title(APP_NAME)
    st.caption("Panel empresarial en construcción")
    st.divider()

    st.subheader("Navegación")
    selected_page = st.radio(
        "Secciones disponibles",
        NAVIGATION_OPTIONS,
        label_visibility="collapsed",
    )

    st.divider()
    st.caption(f"Versión {APP_VERSION}")
    st.caption(f"Estado: {PROJECT_STATUS}")
    st.info(
        "Esta etapa es únicamente descriptiva. No existen operaciones reales, autenticación ni almacenamiento de datos."
    )


def render_home() -> None:
    with st.container(border=True):
        render_page_header(
            APP_NAME,
            "Base visual y estructural del futuro sistema empresarial de CopyMary.",
        )
        st.caption("Etapa actual: interfaz descriptiva y validación de la estructura inicial.")

    st.warning(
        "Sistema en construcción. Esta versión presenta navegación, contenido descriptivo y una primera función temporal; "
        "todavía no guarda información de forma permanente."
    )

    st.subheader("Resumen del proyecto")
    metric_columns = st.columns(4)
    metrics = (
        ("Estado del proyecto", PROJECT_STATUS),
        ("Módulos planificados", str(PLANNED_MODULES)),
        ("Blueprints creados", str(CREATED_BLUEPRINTS)),
        ("Módulos disponibles", str(len(MODULES))),
    )
    for column, (label, value) in zip(metric_columns, metrics, strict=True):
        column.metric(label, value)

    st.divider()
    st.subheader("Módulos actualmente disponibles")
    module_columns = st.columns(2)
    for index, (module_name, module_info) in enumerate(MODULES.items()):
        with module_columns[index % 2]:
            label = "FUNCIÓN TEMPORAL" if module_name == "Configuración General" else "INTERFAZ DESCRIPTIVA"
            render_info_card(
                module_name,
                module_info["description"],
                label,
            )

    st.divider()
    left_column, right_column = st.columns(2)
    with left_column:
        st.subheader("Hitos de esta etapa")
        st.caption("Avances estructurales ya incorporados en la interfaz actual.")
        render_info_card(
            "Estructura inicial organizada",
            "La navegación, la configuración y los componentes visuales se encuentran separados para facilitar su mantenimiento.",
            "COMPLETADO",
        )
        render_info_card(
            "Primera función utilizable",
            "Configuración General permite aplicar parámetros y obtener un resumen calculado durante la sesión.",
            "NUEVO",
        )

    with right_column:
        render_list_section(
            "Próximos pasos",
            [
                "Validar la utilidad de la primera configuración temporal.",
                "Revisar y aprobar el alcance de cada Blueprint.",
                "Diseñar la estrategia de datos antes de seleccionar una base de datos.",
                "Elegir la siguiente función real, pequeña y verificable.",
            ],
        )


def render_module(module_name: str) -> None:
    module_info = MODULES.get(module_name)
    if module_info is None:
        st.error("La sección solicitada no está disponible.")
        return

    with st.container(border=True):
        render_page_header(module_name, module_info["description"])
        st.caption("Alcance actual: documentación visual del módulo y revisión de su Blueprint.")

    st.warning(
        "Este módulo todavía no está desarrollado. La pantalla es informativa y no ejecuta ni guarda operaciones."
    )

    st.subheader("Resumen del módulo")
    status_column, dependency_column = st.columns(2)
    with status_column:
        render_info_card("Estado", module_info["status"], "SITUACIÓN ACTUAL")
    with dependency_column:
        render_info_card(
            "Dependencias",
            " · ".join(module_info["dependencies"]),
            "RELACIONES PREVISTAS",
        )

    st.divider()
    render_info_card("Objetivo", module_info["objective"], "PROPÓSITO")

    st.subheader("Funciones previstas")
    st.caption("Contenido planificado. Ninguna de estas funciones está implementada todavía.")
    for planned_function in module_info["planned_functions"]:
        st.markdown(f"- {planned_function}")

    st.info("No hay formularios, botones operativos, autenticación real ni almacenamiento de datos en esta etapa.")


if selected_page == "Inicio":
    render_home()
elif selected_page == "Configuración General":
    render_general_settings()
elif selected_page in MODULES:
    render_module(selected_page)
else:
    st.error("La opción seleccionada no existe. Regrese a Inicio desde la navegación lateral.")
