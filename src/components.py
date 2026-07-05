"""Componentes visuales reutilizables para la interfaz inicial."""

from collections.abc import Iterable
from html import escape

import streamlit as st

from src.config import COLORS


def apply_base_styles() -> None:
    """Aplica una capa breve de estilos sin dependencias externas."""
    st.markdown(
        f"""
        <style>
            .stApp {{ background-color: {COLORS['background']}; }}
            .block-container {{ padding-top: 2rem; max-width: 1400px; }}
            [data-testid="stSidebar"] {{ background-color: {COLORS['surface']}; }}

            [data-testid="stMetric"] {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 1rem;
                min-height: 118px;
            }}

            [data-testid="stMetricValue"] {{
                font-size: clamp(1.45rem, 2vw, 2.2rem);
            }}

            [data-testid="stMetricValue"] > div {{
                white-space: normal;
                overflow: visible;
                text-overflow: clip;
                line-height: 1.15;
            }}

            .cm-card {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
                padding: 1.1rem 1.2rem;
                margin-bottom: 0.9rem;
                min-height: 146px;
                box-shadow: 0 4px 14px rgba(31, 41, 55, 0.04);
            }}

            .cm-card h4 {{
                color: {COLORS['text']};
                line-height: 1.25;
                margin: 0.35rem 0 0.55rem;
            }}

            .cm-eyebrow {{
                color: {COLORS['primary']};
                font-weight: 700;
                font-size: 0.78rem;
                letter-spacing: 0.04em;
            }}

            .cm-muted {{
                color: {COLORS['muted']};
                line-height: 1.55;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str) -> None:
    st.caption("COPYMARY ERP · BASE FUNCIONAL")
    st.title(title)
    st.write(subtitle)


def render_info_card(title: str, body: str, label: str | None = None) -> None:
    safe_title = escape(title)
    safe_body = escape(body)
    safe_label = escape(label) if label else ""
    label_html = f'<div class="cm-eyebrow">{safe_label}</div>' if label else ""

    st.markdown(
        f'<div class="cm-card">{label_html}<h4>{safe_title}</h4>'
        f'<div class="cm-muted">{safe_body}</div></div>',
        unsafe_allow_html=True,
    )


def render_list_section(title: str, items: Iterable[str]) -> None:
    st.subheader(title)

    for item in items:
        st.markdown(f"- {item}")
        
