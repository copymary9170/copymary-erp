"""Suite de Meta Ads: planificación, audiencias y estructura operativa."""
from __future__ import annotations

import streamlit as st

from src.marketing_meta_ads_planner import render_meta_ads_planner
from src.marketing_meta_ads_execution import render_meta_ads_execution
from src.marketing_audience_lab import render_audience_lab


def render_meta_ads_suite() -> None:
    view = st.radio(
        "Área Meta Ads",
        ("Planificador y auditor", "Audiencias y remarketing", "Estructura y pruebas"),
        horizontal=True,
        label_visibility="collapsed",
        key="marketing_meta_ads_suite_view",
    )
    st.divider()
    if view == "Estructura y pruebas":
        render_meta_ads_execution()
    elif view == "Audiencias y remarketing":
        render_audience_lab()
    else:
        render_meta_ads_planner()
