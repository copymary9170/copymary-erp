"""Entrada unificada del módulo de Marketing."""
from __future__ import annotations

import streamlit as st

from src.marketing_class_center import render_marketing_class_center
from src.marketing_meta_ads_planner import render_meta_ads_planner
from src.marketing_growth_lab import render_growth_lab


def render_marketing() -> None:
    """Renderiza estrategia, crecimiento orgánico y planificación publicitaria."""
    workspace = st.radio(
        "Vista de Marketing",
        ("Centro estratégico", "Crecimiento y comunidad", "Meta Ads"),
        horizontal=True,
        label_visibility="collapsed",
        key="marketing_suite_view",
    )
    st.divider()
    if workspace == "Meta Ads":
        render_meta_ads_planner()
    elif workspace == "Crecimiento y comunidad":
        render_growth_lab()
    else:
        render_marketing_class_center()
