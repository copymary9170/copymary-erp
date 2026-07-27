"""Persistencia automática de Configuración General."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, is_dataclass

import streamlit as st

from src.core_repository import save_entity
from src.session_backup import save_snapshot_to_database
from src.session_store import save_section

LOGGER = logging.getLogger(__name__)
_SETTINGS_FINGERPRINT_KEY = "_general_settings_persisted_fingerprint"


def _settings_payload(settings: object | None) -> dict | None:
    if settings is None:
        return None
    if is_dataclass(settings):
        return asdict(settings)
    if isinstance(settings, dict):
        return dict(settings)
    return None


def settings_fingerprint(settings: object | None) -> str:
    """Huella estable de la configuración para evitar escrituras duplicadas."""
    payload = _settings_payload(settings)
    if payload is None:
        return ""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def persist_general_settings_if_changed() -> bool:
    """Guarda configuración viva y conserva mecanismos históricos compatibles."""
    settings = st.session_state.get("general_settings")
    payload = _settings_payload(settings)
    fingerprint = settings_fingerprint(settings)
    if payload is None or not fingerprint:
        return False
    if st.session_state.get(_SETTINGS_FINGERPRINT_KEY) == fingerprint:
        return False

    # session_store es la fuente viva. Si la BD está caída, save_section registra
    # el modo degradado y la aplicación sigue operando con st.session_state.
    persisted = save_section("general_settings", payload)

    # Mantener core_entities y snapshots durante la transición/migración.
    try:
        save_entity("general_settings", payload)
    except Exception:
        LOGGER.exception("No se pudo actualizar core_entities para general_settings.")
    try:
        save_snapshot_to_database()
    except Exception:
        LOGGER.exception("No se pudo crear el snapshot histórico de general_settings.")

    if persisted:
        st.session_state[_SETTINGS_FINGERPRINT_KEY] = fingerprint
    return persisted
