"""Controles de personalización para Inicio fase 4."""
from __future__ import annotations

import streamlit as st

from src.home_dashboard_preferences import (
    DashboardPreferences,
    PROFILE_WIDGETS,
    load_preferences,
    reset_preferences,
    save_preferences,
)


WIDGET_LABELS = {
    "executive_metrics": "Indicadores ejecutivos",
    "business_flow": "Flujo del negocio",
    "priorities": "Prioridades",
    "agenda": "Agenda y actividad",
    "phase3": "Tendencias y centros operativos",
    "phase5": "Analítica ejecutiva y comparativos",
    "quick_actions": "Acciones rápidas",
    "system_status": "Estado general y técnico",
}


def render_preferences_panel(user_id: str, role_name: str) -> DashboardPreferences:
    current = load_preferences(user_id, role_name)
    with st.expander("Personalizar mi Inicio", expanded=False):
        profile = st.selectbox(
            "Perfil del dashboard",
            options=list(PROFILE_WIDGETS),
            index=list(PROFILE_WIDGETS).index(current.profile),
            help="Cada perfil propone una selección inicial de widgets para el trabajo diario.",
        )
        allowed = PROFILE_WIDGETS[profile]
        selected = st.multiselect(
            "Widgets visibles",
            options=list(allowed),
            default=[widget for widget in current.visible_widgets if widget in allowed] or list(allowed),
            format_func=lambda widget: WIDGET_LABELS.get(widget, widget),
        )
        chart_days = st.select_slider(
            "Periodo de tendencias",
            options=[7, 14, 30],
            value=current.chart_days,
            format_func=lambda value: f"{value} días",
        )
        left, right = st.columns(2)
        if left.button("Guardar preferencias", use_container_width=True, type="primary"):
            save_preferences(
                user_id,
                DashboardPreferences(profile, tuple(selected) or allowed, chart_days),
            )
            st.success("Preferencias guardadas para esta sesión de usuario.")
            st.rerun()
        if right.button("Restaurar predeterminado", use_container_width=True):
            reset_preferences(user_id)
            st.info("Se restauró el perfil recomendado para tu rol.")
            st.rerun()
    return load_preferences(user_id, role_name)
