"""Renderer unificado de Marketing Pro + plan guiado + estrategia de contenido + IA."""
from __future__ import annotations

import streamlit as st

from src import marketing_strategy_suite as strategy
from src.marketing_guided_plan import render_marketing_guided_plan
from src.marketing_content_strategy import render_marketing_content_strategy
from src.marketing_ai_builder import render_marketing_ai_builder


def render_marketing() -> None:
    """Conserva Marketing Pro y agrega metodología guiada, investigación y AI Builder."""
    strategy.render_marketing()
    st.divider()
    render_marketing_guided_plan()
    st.divider()
    render_marketing_content_strategy()
    st.divider()
    render_marketing_ai_builder()
