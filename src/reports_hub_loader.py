"""Registra el centro unificado de Reportes sin duplicar navegación."""
from __future__ import annotations

from src.reports_hub import render_reports_hub


def activate_reports_hub() -> None:
    from src import app_shell, top_navigation_app

    app_shell.FUNCTIONAL_MODULES["Reportes"] = render_reports_hub

    area = "Contabilidad y análisis"
    icon, eyebrow, description, pages = top_navigation_app.SPECIALTY_AREAS[area]
    if "Reportes" not in pages:
        top_navigation_app.SPECIALTY_AREAS[area] = (
            icon,
            eyebrow,
            description,
            (*pages, "Reportes"),
        )
    top_navigation_app.DESCRIPTIONS["Reportes"] = (
        "Documentos, finanzas, históricos, administración, consolidado y egresos."
    )
    top_navigation_app.PAGE_TO_AREA["Reportes"] = area
