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
            }}
            .cm-card {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
                padding: 1rem 1.1rem;
                margin-bottom: 0.9rem;
            }}
            .cm-eyebrow {{ color: {COLORS['primary']}; font-weight: 700; font-size: 0.82rem; }}
            .cm-muted {{ color: {COLORS['muted']}; }}
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
        f'<div class="cm-card">{label_html}<h4>{safe_title}</h4><div class="cm-muted">{safe_body}</div></div>',
        unsafe_allow_html=True,
    )


def render_list_section(title: str, items: Iterable[str]) -> None:
    st.subheader(title)
    for item in items:
        st.markdown(f"- {item}")
