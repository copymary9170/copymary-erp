"""Registro de proveedores ampliados."""

from src import app_shell
from src.suppliers_intelligence import render_suppliers_intelligence

app_shell.FUNCTIONAL_MODULES["Proveedores"] = render_suppliers_intelligence
