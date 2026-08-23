"""Entrada unificada del módulo de Marketing."""
from __future__ import annotations

from src.marketing_workspace import render_marketing_workspace


def render_marketing() -> None:
    """Renderiza Marketing como workspace con navegación interna."""
    render_marketing_workspace()
