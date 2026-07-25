"""Preparación segura del historial persistente de salud de Inventario.

La vista documenta y permite descargar la migración propuesta. No ejecuta SQL,
no crea tablas y no guarda observaciones automáticamente.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st


_MIGRATION_PATH = Path("migrations/20260725_inventory_health_snapshots.sql")


def _migration_text() -> str:
    try:
        return _MIGRATION_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def render_inventory_health_history_readiness() -> None:
    """Muestra el diseño de persistencia sin alterar la base de datos."""
    st.divider()
    st.subheader("Preparación del historial persistente")
    st.caption(
        "Fase de preparación y revisión. La aplicación no ejecuta la migración ni guarda observaciones persistentes."
    )

    columns = st.columns(4)
    columns[0].metric("Migración", "Preparada")
    columns[1].metric("Ejecución automática", "Desactivada")
    columns[2].metric("Auditoría", "Fecha y usuario")
    columns[3].metric("Impacto operativo", "Ninguno")

    st.markdown(
        "**Campos propuestos:** fecha de medición, usuario, índice de salud, completitud, "
        "cantidad de artículos, hallazgos por prioridad, estado general, versión del cálculo y notas."
    )

    st.info(
        "Antes de habilitar la escritura se debe revisar la migración, definir permisos de lectura y escritura, "
        "confirmar la identidad del usuario autenticado y probar respaldo y reversión."
    )

    sql = _migration_text()
    if sql:
        with st.expander("Ver migración propuesta"):
            st.code(sql, language="sql")
        st.download_button(
            "Descargar migración SQL",
            data=sql.encode("utf-8"),
            file_name="20260725_inventory_health_snapshots.sql",
            mime="text/sql",
            key="inventory_health_history_migration_download",
        )
    else:
        st.warning("No se encontró el archivo de migración en el entorno actual.")

    st.warning(
        "Esta fase no habilita el botón para guardar historial. La escritura persistente debe añadirse "
        "en una fase posterior, después de aplicar y verificar la migración de forma controlada."
    )
