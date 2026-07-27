"""Almacén persistente genérico para las secciones históricas de sesión.

La sesión sigue siendo la caché inmediata de Streamlit, mientras ``session_store``
es la fuente durable. Todos los fallos de base de datos degradan de forma explícita
a modo solo-sesión y se registran; nunca derriban la aplicación.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import logging
from typing import Any

import streamlit as st

from src.erp_database import connect, initialize_database
from src.session_utils import now_iso

LOGGER = logging.getLogger(__name__)
DEGRADED_KEY = "_session_store_degraded"
STARTUP_MARKER = "_session_store_hydrated"


def _serializable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serializable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    return value


def _mark_degraded(operation: str, exc: Exception) -> None:
    message = f"Persistencia degradada durante {operation}: {exc}"
    LOGGER.exception(message)
    try:
        st.session_state[DEGRADED_KEY] = message
    except Exception:
        pass


def ensure_session_store_table() -> bool:
    """Crea la tabla idempotente en SQLite o PostgreSQL."""
    try:
        initialize_database()
        with connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS session_store (
                    section TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
        return True
    except Exception as exc:
        _mark_degraded("inicializar session_store", exc)
        return False


def save_section(section: str, value: Any) -> bool:
    """Hace UPSERT de una sola sección; devuelve False en modo degradado."""
    if not section:
        raise ValueError("La sección no puede estar vacía.")
    try:
        if not ensure_session_store_table():
            return False
        payload = json.dumps(_serializable(value), ensure_ascii=False, sort_keys=True, default=str)
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO session_store(section, data_json, updated_at_utc)
                VALUES (?, ?, ?)
                ON CONFLICT(section) DO UPDATE SET
                    data_json = excluded.data_json,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (section, payload, now_iso()),
            )
        st.session_state.pop(DEGRADED_KEY, None)
        return True
    except Exception as exc:
        _mark_degraded(f"guardar '{section}'", exc)
        return False


def load_section(section: str) -> tuple[bool, Any]:
    """Devuelve ``(existe, valor)`` sin lanzar por indisponibilidad de BD."""
    try:
        if not ensure_session_store_table():
            return False, None
        with connect() as connection:
            row = connection.execute(
                "SELECT data_json FROM session_store WHERE section = ?",
                (section,),
            ).fetchone()
        if row is None:
            return False, None
        return True, json.loads(row["data_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        _mark_degraded(f"deserializar '{section}'", exc)
        return False, None
    except Exception as exc:
        _mark_degraded(f"leer '{section}'", exc)
        return False, None


def section_exists(section: str) -> bool:
    exists, _ = load_section(section)
    return exists


def migrate_section_if_missing(section: str, value: Any) -> bool:
    """Migra una sección una sola vez, sin pisar datos persistidos."""
    exists, _ = load_section(section)
    if exists or value is None:
        return False
    return save_section(section, value)


def _known_sections() -> tuple[str, ...]:
    from src.session_backup import SESSION_KEYS

    return tuple(dict.fromkeys(SESSION_KEYS))


def _hydrate_value(section: str, raw: Any) -> Any:
    if section != "general_settings":
        return raw
    if raw is None or is_dataclass(raw):
        return raw
    from src.session_backup import _settings

    return _settings(raw)


def hydrate_session_store_on_startup() -> dict[str, int]:
    """Hidrata claves ausentes y migra el snapshot heredado de forma idempotente.

    Nunca reemplaza una clave ya presente en ``st.session_state``. Si el arranque
    histórico restauró un snapshot y la tabla aún no contiene esa sección, ese
    valor se migra una sola vez.
    """
    if st.session_state.get(STARTUP_MARKER):
        return {"loaded": 0, "migrated": 0}

    loaded = migrated = 0
    for section in _known_sections():
        if section in st.session_state:
            if migrate_section_if_missing(section, st.session_state.get(section)):
                migrated += 1
            continue
        exists, raw = load_section(section)
        if not exists:
            continue
        try:
            value = _hydrate_value(section, raw)
        except Exception as exc:
            _mark_degraded(f"hidratar '{section}'", exc)
            continue
        if value is not None:
            st.session_state[section] = value
            loaded += 1

    st.session_state[STARTUP_MARKER] = True
    return {"loaded": loaded, "migrated": migrated}
