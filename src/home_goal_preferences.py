"""Metas reversibles por usuario para Inicio fase 6A.

Esta fase no crea tablas ni migraciones. Las metas se guardan en ``st.session_state``
por usuario autenticado y pueden restaurarse a sus valores predeterminados.
"""
from __future__ import annotations

import streamlit as st

from src.home_kpi_registry import KPI_DEFINITIONS


def _storage_key(user_id: str) -> str:
    return f"home_dashboard_goals::{user_id or 'anonymous'}"


def default_goals() -> dict[str, float]:
    return {definition.key: float(definition.target) for definition in KPI_DEFINITIONS}


def load_goals(user_id: str) -> dict[str, float]:
    stored = st.session_state.get(_storage_key(user_id))
    defaults = default_goals()
    if not isinstance(stored, dict):
        return defaults
    result = defaults.copy()
    for key, value in stored.items():
        if key not in result:
            continue
        try:
            result[key] = max(float(value), 0.0)
        except (TypeError, ValueError):
            continue
    return result


def save_goals(user_id: str, goals: dict[str, float]) -> None:
    defaults = default_goals()
    st.session_state[_storage_key(user_id)] = {
        key: max(float(goals.get(key, value)), 0.0)
        for key, value in defaults.items()
    }


def reset_goals(user_id: str) -> None:
    st.session_state.pop(_storage_key(user_id), None)
