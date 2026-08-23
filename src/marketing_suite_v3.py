"""Renderer unificado de Marketing Pro + plan + contenido + video + UGC/TikTok + mercado/Ads + IA."""
from __future__ import annotations

import streamlit as st

from src import marketing_strategy_suite as strategy
from src.marketing_guided_plan import render_marketing_guided_plan
from src.marketing_content_strategy import render_marketing_content_strategy
from src.marketing_story_video import render_marketing_story_video
from src.marketing_ugc_tiktok import render_marketing_ugc_tiktok
from src.marketing_insights_meta import render_marketing_insights_meta
from src.marketing_ai_builder import render_marketing_ai_builder


def render_marketing() -> None:
    """Marketing Pro completo: estrategia, investigación, producción, experimentación, paid media e IA."""
    strategy.render_marketing()
    st.divider()
    render_marketing_guided_plan()
    st.divider()
    render_marketing_content_strategy()
    st.divider()
    render_marketing_story_video()
    st.divider()
    render_marketing_ugc_tiktok()
    st.divider()
    render_marketing_insights_meta()
    st.divider()
    render_marketing_ai_builder()
