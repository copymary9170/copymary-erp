"""Preferencias reversibles del dashboard de Inicio.

Esta fase evita migraciones: la configuración se mantiene en ``st.session_state``
por usuario autenticado. La arquitectura queda preparada para persistencia futura
sin alterar la lógica operativa del ERP.
"""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


PROFILE_WIDGETS: dict[str, tuple[str, ...]] = {
    "Gerencia": (
        "executive_metrics",
        "business_flow",
        "priorities",
        "agenda",
        "phase3",
        "phase5",
        "phase6",
        "quick_actions",
        "system_status",
    ),
    "Ventas": (
        "executive_metrics",
        "priorities",
        "agenda",
        "phase3",
        "phase5",
        "phase6",
        "quick_actions",
    ),
    "Compras": (
        "executive_metrics",
        "business_flow",
        "priorities",
        "agenda",
        "phase5",
        "phase6",
        "quick_actions",
    ),
    "Inventario": (
        "business_flow",
        "priorities",
        "phase3",
        "phase5",
        "phase6",
        "quick_actions",
        "system_status",
    ),
    "Producción": (
        "executive_metrics",
        "business_flow",
        "priorities",
        "agenda",
        "phase5",
        "phase6",
        "quick_actions",
    ),
}


@dataclass(frozen=True)
class DashboardPreferences:
    profile: str
    visible_widgets: tuple[str, ...]
    chart_days: int


def _storage_key(user_id: str) -> str:
    return f"home_dashboard_preferences::{user_id or 'anonymous'}"


def default_preferences(role_name: str) -> DashboardPreferences:
    normalized = str(role_name or "").casefold()
    if "venta" in normalized or "comercial" in normalized:
        profile = "Ventas"
    elif "compra" in normalized or "abaste" in normalized:
        profile = "Compras"
    elif "invent" in normalized or "almac" in normalized:
        profile = "Inventario"
    elif "produc" in normalized:
        profile = "Producción"
    else:
        profile = "Gerencia"
    return DashboardPreferences(profile, PROFILE_WIDGETS[profile], 7)


def load_preferences(user_id: str, role_name: str) -> DashboardPreferences:
    stored = st.session_state.get(_storage_key(user_id))
    if not isinstance(stored, dict):
        return default_preferences(role_name)
    profile = stored.get("profile")
    if profile not in PROFILE_WIDGETS:
        return default_preferences(role_name)
    valid_widgets = tuple(
        widget for widget in stored.get("visible_widgets", ())
        if widget in PROFILE_WIDGETS[profile]
    )
    chart_days = int(stored.get("chart_days", 7))
    if chart_days not in {7, 14, 30}:
        chart_days = 7
    return DashboardPreferences(profile, valid_widgets or PROFILE_WIDGETS[profile], chart_days)


def save_preferences(user_id: str, preferences: DashboardPreferences) -> None:
    st.session_state[_storage_key(user_id)] = {
        "profile": preferences.profile,
        "visible_widgets": list(preferences.visible_widgets),
        "chart_days": preferences.chart_days,
    }


def reset_preferences(user_id: str) -> None:
    st.session_state.pop(_storage_key(user_id), None)
