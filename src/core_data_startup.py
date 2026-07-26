"""Carga y migración segura de datos núcleo al iniciar CopyMary ERP."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass

import streamlit as st

from src.core_repository import CORE_ENTITY_KEYS, CORE_LIST_KEYS, load_entity, migrate_entity_if_missing
from src.startup_restore import _active_general_settings

_STARTUP_MARKER = "_core_data_startup_loaded"


def _legacy_value(key: str) -> object | None:
    value = st.session_state.get(key)
    if is_dataclass(value):
        return asdict(value)
    return value


def _hydrate_general_settings(raw: object) -> object | None:
    if raw is None:
        return None
    if is_dataclass(raw):
        return raw
    return _active_general_settings(raw)


def load_core_data_on_startup() -> None:
    """Migra datos heredados una sola vez y carga la BD como fuente principal.

    La migración nunca sobrescribe una entidad ya persistida. Una entidad vacía
    en la base también se considera existente y, por tanto, autoritativa.
    """
    if st.session_state.get(_STARTUP_MARKER):
        return

    for key in CORE_ENTITY_KEYS:
        persisted = load_entity(key)
        if persisted is None:
            legacy = _legacy_value(key)
            if legacy is not None:
                migrate_entity_if_missing(key, legacy)
                persisted = load_entity(key)
        if persisted is None:
            continue
        if key == "general_settings":
            settings = _hydrate_general_settings(persisted)
            if settings is not None:
                st.session_state[key] = settings
        elif key in CORE_LIST_KEYS:
            if not isinstance(persisted, list) or any(not isinstance(item, dict) for item in persisted):
                raise ValueError(f"La entidad persistida '{key}' debe ser una lista de objetos.")
            st.session_state[key] = [dict(item) for item in persisted]

    st.session_state[_STARTUP_MARKER] = True
