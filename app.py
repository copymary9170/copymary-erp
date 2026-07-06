"""Punto de entrada de CopyMary ERP."""
from src import app_shell
from src.app_shell_payments import run_app
from src.control_center_today import render_control_center_today

app_shell.FUNCTIONAL_MODULES["Centro de control"] = render_control_center_today
run_app()
