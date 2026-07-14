"""Activa la pantalla de cotizaciones basada en procesos productivos."""


def activate_process_quotes() -> None:
    from src import app_shell
    from src.quotes_process import render_process_quotes

    app_shell.FUNCTIONAL_MODULES["Cotizaciones"] = render_process_quotes
