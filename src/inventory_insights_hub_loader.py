"""Consolida diagnósticos complementarios de Inventario en una sola superficie.

Este loader no reemplaza lógica de negocio: conserva el renderer vigente y agrupa
los paneles de calidad, planificación y salud que antes se apilaban uno debajo
del otro mediante múltiples wrappers.
"""
import streamlit as st

from src import app_shell
from src.inventory_consistency_rules_safe import render_inventory_consistency_rules
from src.inventory_data_quality_safe import render_inventory_data_quality
from src.inventory_health_history_readiness_safe import render_inventory_health_history_readiness
from src.inventory_health_history_safe import render_inventory_health_history
from src.inventory_health_summary_safe import render_inventory_health_summary
from src.inventory_health_trend_safe import render_inventory_health_trend
from src.inventory_priority_summary_safe import render_inventory_priority_summary
from src.inventory_review_plan_safe import render_inventory_review_plan


def render_inventory_insights_hub() -> None:
    """Agrupa paneles auxiliares sin alterar sus implementaciones internas."""
    st.divider()
    st.subheader("Diagnóstico y seguimiento de inventario")
    st.caption(
        "Calidad, planificación y salud se agrupan aquí para evitar paneles repetidos "
        "y mantener cada herramienta disponible en una sola zona."
    )

    quality_tab, planning_tab, health_tab = st.tabs(("Calidad", "Planificación", "Salud"))

    with quality_tab:
        data_tab, rules_tab = st.tabs(("Calidad de datos", "Reglas de consistencia"))
        with data_tab:
            render_inventory_data_quality()
        with rules_tab:
            render_inventory_consistency_rules()

    with planning_tab:
        priorities_tab, review_tab = st.tabs(("Prioridades", "Plan de revisión"))
        with priorities_tab:
            render_inventory_priority_summary()
        with review_tab:
            render_inventory_review_plan()

    with health_tab:
        summary_tab, trend_tab, readiness_tab, history_tab = st.tabs(
            ("Resumen", "Tendencia", "Preparación del historial", "Historial")
        )
        with summary_tab:
            render_inventory_health_summary()
        with trend_tab:
            render_inventory_health_trend()
        with readiness_tab:
            render_inventory_health_history_readiness()
        with history_tab:
            render_inventory_health_history()


def activate_inventory_insights_hub() -> None:
    """Añade un único hub después del renderer vigente de Inventario."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Inventario")
    if current_renderer is None:
        return

    def render_inventory_with_insights_hub() -> None:
        current_renderer()
        render_inventory_insights_hub()

    app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_with_insights_hub
