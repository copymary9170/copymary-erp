"""Persistencia automática de Configuración General.

La configuración activa vive en ``st.session_state``. Este módulo detecta
cambios y crea un snapshot en la base de datos sin exigir que el usuario vaya
a Respaldos y pulse otro botón después de guardar las tasas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass

import streamlit as st

from src.session_backup import save_snapshot_to_database

_SETTINGS_FINGERPRINT_KEY = "_general_settings_persisted_fingerprint"


def _settings_payload(settings: object | None) -> dict | None:
    if settings is None:
        return None
    if is_dataclass(settings):
        return asdict(settings)
    if isinstance(settings, dict):
        return settings
    return None


def settings_fingerprint(settings: object | None) -> str:
    """Huella estable de la configuración para evitar snapshots duplicados."""
    payload = _settings_payload(settings)
    if payload is None:
        return ""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def persist_general_settings_if_changed() -> bool:
    """Guarda un snapshot cuando Configuración General cambió.

    Devuelve ``True`` si se creó un respaldo y ``False`` si no había cambios o
    si la base de datos no estaba disponible. Un fallo de persistencia nunca
    debe borrar lo que ya quedó guardado en la sesión activa.
    """
    settings = st.session_state.get("general_settings")
    fingerprint = settings_fingerprint(settings)
    if not fingerprint:
        return False
    if st.session_state.get(_SETTINGS_FINGERPRINT_KEY) == fingerprint:
        return False

    try:
        save_snapshot_to_database()
    except Exception:
        return False

    st.session_state[_SETTINGS_FINGERPRINT_KEY] = fingerprint
    return True
