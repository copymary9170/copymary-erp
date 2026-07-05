"""Extensión de navegación para las metas del negocio."""

from src import app_shell
from src.business_goals import render_business_goals


app_shell.FUNCTIONAL_MODULES["Metas del negocio"] = render_business_goals
app_shell.NAVIGATION_GROUPS["Inicio"] = (
    "Inicio",
    "Centro de control",
    "Auditoría de datos",
    "Metas del negocio",
    "Panel comercial",
    "Panel financiero y cierres",
)


def run_app() -> None:
    app_shell.run_app()
