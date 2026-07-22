"""Restauración segura del respaldo al iniciar CopyMary ERP.

Streamlit vuelve a ejecutar ``app.py`` en cada interacción. Este módulo evita
restaurar repetidamente y, cuando la sesión ya contiene clientes, ventas u
otros registros, recupera únicamente ``general_settings`` para no sobrescribir
el trabajo activo.
"""

from __future__ import annotations

import streamlit as st

from src.erp_database import connect, initialize_database
from src.session_backup import (
    _parse_backup,
    _restore,
    restore_latest_snapshot_from_database,
    session_has_data,
)

_STARTUP_RESTORE_MARKER = "_session_snapshot_startup_restore_done"


def _restore_general_settings_from_latest_snapshot() -> None:
    """Recupera solo Configuración General desde el snapshot más reciente."""
    initialize_database()
    with connect() as conn:
        row = conn.execute(
            "SELECT data_json FROM session_snapshots "
            "ORDER BY created_at_utc DESC LIMIT 1"
        ).fetchone()

    if row is None:
        return

    restored = _parse_backup(row["data_json"].encode("utf-8"))
    if "general_settings" not in restored["present_sections"]:
        return
    if restored["general_settings"] is None:
        return

    _restore(restored, ["general_settings"])


def restore_session_snapshot_on_startup() -> None:
    """Restaura el snapshot una sola vez por sesión de Streamlit.

    - Sesión vacía: restaura todas las secciones.
    - Sesión con datos: restaura únicamente ``general_settings``.

    La segunda ruta corrige el caso en que clientes, cotizaciones u otros
    registros ya existen y hacían que la restauración completa se omitiera,
    dejando perder las tasas BCV, Binance, Kontigo, IVA, IGTF y comisiones.
    Los errores de base de datos se ignoran para no impedir el arranque.
    """
    if st.session_state.get(_STARTUP_RESTORE_MARKER):
        return

    try:
        if session_has_data():
            _restore_general_settings_from_latest_snapshot()
        else:
            restore_latest_snapshot_from_database()
    except Exception:
        pass
    finally:
        st.session_state[_STARTUP_RESTORE_MARKER] = True
