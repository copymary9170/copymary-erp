"""Utilidades compartidas para datos de sesión y entidades persistentes."""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st


def now_iso() -> str:
    """Marca de tiempo UTC en formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def read_list(key: str) -> list[dict]:
    """Lee una colección, priorizando la base de datos para entidades núcleo."""
    from src.core_repository import CORE_LIST_KEYS, load_list, migrate_entity_if_missing

    if key in CORE_LIST_KEYS:
        persisted = load_list(key)
        if persisted is not None:
            st.session_state[key] = persisted
            return [dict(item) for item in persisted]
        legacy_rows = [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]
        if legacy_rows:
            migrate_entity_if_missing(key, legacy_rows)
        return legacy_rows
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def save_list(key: str, rows: list[dict]) -> None:
    """Guarda una colección en sesión y, si es núcleo, también en base de datos."""
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise ValueError("Los datos deben ser una lista de objetos.")
    copied = [dict(item) for item in rows]
    from src.core_repository import CORE_LIST_KEYS, save_entity

    if key in CORE_LIST_KEYS:
        save_entity(key, copied)
    st.session_state[key] = copied


def item_name(item_id: str, items: list[dict]) -> str:
    """Busca el nombre de un ítem de inventario por su id."""
    for item in items:
        if str(item.get("item_id", "")) == item_id:
            return str(item.get("name", "Material"))
    return "Material no disponible"
