"""Extensión de navegación para reversos de pagos."""

from src import app_shell
from src.app_shell_goals import run_app as _run_base_app
from src.payment_consistency import activate_payment_consistency
from src.payment_reversals import render_payment_reversals


activate_payment_consistency()
app_shell.FUNCTIONAL_MODULES["Reversos de pagos"] = render_payment_reversals
app_shell.NAVIGATION_GROUPS["Administración"] = (
    "Caja",
    "Gastos y presupuesto",
    "Equipo y comisiones",
    "Reversos de pagos",
    "Anulaciones y ajustes",
    "Activos",
    "Respaldar activos",
    "Configuración General",
    "Respaldo general",
)


def run_app() -> None:
    _run_base_app()
