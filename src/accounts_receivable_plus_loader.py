"""Registro del módulo ampliado de cuentas por cobrar."""

from src import app_shell
from src.accounts_receivable_control import render_accounts_receivable_control

app_shell.FUNCTIONAL_MODULES["Cuentas por cobrar"] = render_accounts_receivable_control
