"""Panel de estado de la fundación técnica."""

from datetime import date

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.erp_database import get_database_status, initialize_database


def render_foundation_status() -> None:
    render_page_header("Fundación técnica", "Estado inicial de datos persistentes para CopyMary ERP.")

    status = get_database_status()
    cols = st.columns(4)
    cols[0].metric("Motor", status.engine)
    cols[1].metric("Esquema", str(status.schema_version))
    cols[2].metric("Estado", "Listo" if status.ready else "Pendiente")
    cols[3].metric("Fecha", date.today().isoformat())

    st.caption(f"Ubicación: {status.location}")
    st.info(status.message)

    if st.button("Inicializar base fundacional", type="primary", use_container_width=True):
        initialize_database()
        st.rerun()

    render_info_card("Alcance", "Esta fase agrega la capa inicial de persistencia sin romper los módulos actuales.", "FASE 1")


app_shell.FUNCTIONAL_MODULES["Fundación técnica"] = render_foundation_status
