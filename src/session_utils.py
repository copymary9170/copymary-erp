"""Utilidades compartidas para datos de sesión con persistencia write-through."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st


def now_iso() -> str:
    """Marca de tiempo UTC en formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def _load_persisted(key: str) -> tuple[bool, Any]:
    from src.session_store import load_section

    return load_section(key)


def _persist(key: str, value: Any) -> bool:
    from src.session_store import save_section

    return save_section(key, value)


def read_list(key: str) -> list[dict]:
    """Lee una lista desde sesión o, si falta, desde la base persistente.

    La clave se carga de forma perezosa y queda cacheada en ``st.session_state``.
    Datos persistidos inválidos se ignoran de forma segura y producen una lista
    vacía; el error queda registrado por ``session_store``.
    """
    if key not in st.session_state:
        exists, persisted = _load_persisted(key)
        if exists and isinstance(persisted, list):
            st.session_state[key] = persisted
        elif exists:
            st.session_state[key] = []
    value = st.session_state.get(key, [])
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def save_list(key: str, rows: list[dict]) -> None:
    """Guarda una lista en sesión y hace UPSERT de esa sección en la BD."""
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise ValueError("Los datos deben ser una lista de objetos.")
    copied = [dict(item) for item in rows]
    st.session_state[key] = copied
    _persist(key, copied)


def read_dict(key: str) -> dict:
    """Lee un diccionario desde sesión o lo recupera perezosamente de la BD."""
    if key not in st.session_state:
        exists, persisted = _load_persisted(key)
        st.session_state[key] = dict(persisted) if exists and isinstance(persisted, dict) else {}
    value = st.session_state.get(key, {})
    return dict(value) if isinstance(value, dict) else {}


def save_dict(key: str, value: dict) -> None:
    """Guarda un diccionario en sesión y hace UPSERT de esa sección en la BD."""
    if not isinstance(value, dict):
        raise ValueError("Los datos deben ser un objeto.")
    copied = dict(value)
    st.session_state[key] = copied
    _persist(key, copied)


def item_name(item_id: str, items: list[dict]) -> str:
    """Busca el nombre de un ítem de inventario por su id."""
    for item in items:
        if str(item.get("item_id", "")) == item_id:
            return str(item.get("name", "Material"))
    return "Material no disponible"
