"""Punto de entrada de CopyMary ERP."""
from src.app_shell_payments import run_app
from src.module_bootstrap import activate_module_bootstrap

activate_module_bootstrap()
run_app()
