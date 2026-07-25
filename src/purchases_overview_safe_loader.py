"""Activa el resumen operativo seguro de Compras."""
from src import app_shell
from src.purchases_overview_safe import render_purchases_overview_safe


def activate_purchases_overview_safe() -> None:
    """Añade el resumen después de la pantalla vigente sin reemplazar su lógica."""
    current_renderer = app_shell.FUNCTIONAL_MODULES.get("Compras")
    if current_renderer is None:
        return

    def render_purchases_with_overview() -> None:
        current_renderer()
        st_divider = __import__("streamlit").divider
        st_divider()
        render_purchases_overview_safe()

    app_shell.FUNCTIONAL_MODULES["Compras"] = render_purchases_with_overview
