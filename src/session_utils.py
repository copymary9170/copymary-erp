"""Utilidades compartidas de `st.session_state` para CopyMary ERP.

Estas funciones existían duplicadas de forma idéntica en más de 80 módulos
(`_now`, `_records`/`_rows`, `_save`). Se centralizan aquí para que:

- un cambio futuro (por ejemplo, mover estas listas a `erp_database`) se haga
  en un solo lugar en vez de en decenas de archivos;
- quede claro, con pruebas, cuál es el comportamiento esperado;
- se reduzca el riesgo de que una copia se actualice y otra quede desincronizada.

No cambia ningún comportamiento existente: cada función reproduce exactamente
el cuerpo que estaba repetido en los módulos originales.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st


def now_iso() -> str:
    """Marca de tiempo UTC en formato ISO 8601 (idéntica en todos los módulos)."""
    return datetime.now(timezone.utc).isoformat()


def read_list(key: str) -> list[dict]:
    """Lee una lista de dicts desde `st.session_state`, ignorando entradas no-dict."""
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def save_list(key: str, rows: list[dict]) -> None:
    """Guarda una lista de dicts en `st.session_state`."""
    st.session_state[key] = rows
