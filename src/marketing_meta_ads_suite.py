"""Suite de Meta Ads: planificación previa + estructura operativa."""
from __future__ import annotations

import streamlit as st

from src.marketing_meta_ads_planner import render_meta_ads_planner
from src.marketing_meta_ads_execution import render_meta_ads_execution


def render_meta_ads_suite() -> None:
    view = st.radio(
        "Área Meta Ads",
        ("Planificador y auditor", "Estructura y pruebas"),
        horizontal=True,
        label_visibility="collapsed",
        key="marketing_meta_ads_suite_view",
    )
    st.divider()
    if view == "Estructura y pruebas":
        render_meta_ads_execution()
    else:
        render_meta_ads_planner()
