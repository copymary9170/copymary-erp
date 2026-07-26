"""Activa el panel ejecutivo seguro de Inicio."""
from src import app_shell
from src.home_dashboard_safe import render_home_dashboard_safe


def activate_home_dashboard_safe() -> None:
    """Sustituye solo el renderer de Inicio y conserva los módulos operativos."""
    app_shell.render_home = render_home_dashboard_safe
