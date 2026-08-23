"""Renderer unificado de Marketing Pro + IA."""
from __future__ import annotations

import streamlit as st

from src import marketing_strategy_suite as strategy
from src.marketing_ai_builder import render_marketing_ai_builder


def render_marketing() -> None:
    """Conserva Marketing Pro y agrega AI Builder como capa final integrada."""
    strategy.render_marketing()
    st.divider()
    render_marketing_ai_builder()
