import streamlit as st


st.set_page_config(
    page_title="CopyMary ERP",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


MODULES = [
    "Gobierno Empresarial",
    "Seguridad",
    "Usuarios, Roles y Permisos",
    "Auditoría y Trazabilidad",
    "Configuración General",
]


with st.sidebar:
    st.title("⚛️ CopyMary ERP")
    selected_module = st.radio(
        "Navegación",
        ["Inicio", *MODULES],
    )
    st.divider()
    st.caption("Versión inicial funcional")


if selected_module == "Inicio":
    st.title("CopyMary ERP")
    st.subheader("Sistema empresarial de CopyMary")

    st.info(
        "Esta es la primera versión funcional del nuevo repositorio. "
        "La arquitectura se diseña en la rama `arquitectura-base` y el código estable vive en `main`."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Módulos planificados", "22")

    with col2:
        st.metric("Blueprints iniciales", "5")

    with col3:
        st.metric("Estado", "En construcción")

    st.divider()
    st.subheader("Fundaciones del sistema")

    for index, module in enumerate(MODULES, start=1):
        st.write(f"{index}. {module}")

    st.warning(
        "Los módulos todavía no realizan operaciones empresariales. "
        "Primero se está construyendo una base segura y comprobable."
    )

else:
    st.title(selected_module)
    st.write(
        "Este módulo está definido a nivel de arquitectura y será desarrollado "
        "después de aprobar su Blueprint."
    )

    st.status("Estado del módulo", expanded=True).write(
        "Blueprint inicial creado. Desarrollo funcional pendiente."
    )

    st.subheader("Próximos pasos")
    st.write("1. Revisar y aprobar el alcance.")
    st.write("2. Definir datos, permisos y formularios.")
    st.write("3. Construir una función pequeña.")
    st.write("4. Probarla antes de continuar.")
