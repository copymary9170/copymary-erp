"""Entrada unificada del módulo de Marketing."""
from __future__ import annotations

import streamlit as st

from src.marketing_class_center import render_marketing_class_center
from src.marketing_meta_ads_suite import render_meta_ads_suite
from src.marketing_growth_lab import render_growth_lab
from src.marketing_intelligence_hub import render_marketing_intelligence_hub
from src.marketing_optimization_cycle import render_marketing_optimization_cycle


def render_marketing() -> None:
    """Renderiza diagnóstico, estrategia, inteligencia, crecimiento y publicidad."""
    workspace = st.radio(
        "Vista de Marketing",
        ("Rendimiento", "Centro estratégico", "Inteligencia", "Crecimiento y comunidad", "Meta Ads"),
        horizontal=True,
        label_visibility="collapsed",
        key="marketing_suite_view",
    )
    st.divider()
    if workspace == "Rendimiento":
        render_marketing_optimization_cycle()
    elif workspace == "Meta Ads":
        render_meta_ads_suite()
    elif workspace == "Crecimiento y comunidad":
        render_growth_lab()
    elif workspace == "Inteligencia":
        render_marketing_intelligence_hub()
    else:
        render_marketing_class_center()
