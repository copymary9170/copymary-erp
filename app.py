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
    st.caption(f"Versión {APP_VERSION}")
    selected_page = st.radio("Navegación", NAVIGATION_OPTIONS)
    st.divider()
    st.info("Interfaz inicial. Sin operaciones empresariales ni almacenamiento de datos.")


def render_home() -> None:
    render_page_header(
        APP_NAME,
        "Base visual y estructural del futuro sistema empresarial de CopyMary.",
    )
    st.warning(
        "Sistema en construcción. Esta versión presenta únicamente navegación y contenido descriptivo; "
        "no guarda información ni ejecuta procesos empresariales."
    )

    metric_columns = st.columns(4)
    metrics = (
        ("Estado del proyecto", PROJECT_STATUS),
        ("Módulos planificados", str(PLANNED_MODULES)),
        ("Blueprints creados", str(CREATED_BLUEPRINTS)),
        ("Módulos disponibles", str(len(MODULES))),
    )
    for column, (label, value) in zip(metric_columns, metrics, strict=True):
        column.metric(label, value)

    st.subheader("Módulos actualmente disponibles")
    module_columns = st.columns(2)
    for index, (module_name, module_info) in enumerate(MODULES.items()):
        with module_columns[index % 2]:
            render_info_card(
                module_name,
                module_info["description"],
                "INTERFAZ DESCRIPTIVA",
            )

    left_column, right_column = st.columns(2)
    with left_column:
        st.subheader("Actividad reciente")
        st.caption("Demostración · Los siguientes datos no representan actividad real.")
        render_info_card(
            "Estructura inicial organizada",
            "Dato de ejemplo: se separó la navegación, configuración y contenido descriptivo.",
            "DEMOSTRACIÓN",
        )
        render_info_card(
            "Módulos fundacionales visibles",
            "Dato de ejemplo: cinco módulos aparecen disponibles para consulta descriptiva.",
            "DEMOSTRACIÓN",
        )

    with right_column:
        render_list_section(
            "Próximos pasos",
            [
                "Revisar y aprobar el alcance de cada Blueprint.",
                "Definir un modelo de usuarios, roles y permisos sin implementarlo todavía.",
                "Diseñar la estrategia de datos antes de seleccionar una base de datos.",
                "Desarrollar una sola función real, pequeña y verificable.",
            ],
        )


def render_module(module_name: str) -> None:
    module_info = MODULES.get(module_name)
    if module_info is None:
        st.error("La sección solicitada no está disponible.")
        return

    render_page_header(module_name, module_info["description"])
    st.warning(
        "Este módulo todavía no está desarrollado. La pantalla es informativa y no ejecuta ni guarda operaciones."
    )

    status_column, dependency_column = st.columns(2)
    with status_column:
        render_info_card("Estado", module_info["status"], "SITUACIÓN ACTUAL")
    with dependency_column:
        render_info_card(
            "Dependencias",
            " · ".join(module_info["dependencies"]),
            "RELACIONES PREVISTAS",
        )

    render_info_card("Objetivo", module_info["objective"], "PROPÓSITO")
    render_list_section("Funciones previstas", module_info["planned_functions"])
    st.info("No hay formularios, botones operativos, autenticación real ni almacenamiento de datos en esta etapa.")


if selected_page == "Inicio":
    render_home()
elif selected_page in MODULES:
    render_module(selected_page)
else:
    st.error("La opción seleccionada no existe. Regrese a Inicio desde la navegación lateral.")
