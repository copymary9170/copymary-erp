"""Entrada unificada del módulo de Marketing."""
from __future__ import annotations

import streamlit as st

from src.marketing_class_center import render_marketing_class_center
from src.marketing_meta_ads_planner import render_meta_ads_planner


def render_marketing() -> None:
    """Renderiza estrategia orgánica y planificación publicitaria en un solo módulo."""
    workspace = st.radio(
        "Vista de Marketing",
        ("Centro estratégico", "Meta Ads"),
        horizontal=True,
        label_visibility="collapsed",
        key="marketing_suite_view",
    )
    st.divider()
    if workspace == "Meta Ads":
        render_meta_ads_planner()
    else:
        render_marketing_class_center()
