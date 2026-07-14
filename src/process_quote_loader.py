"""Activa pantallas basadas en procesos productivos."""


def activate_process_quotes() -> None:
    from src import app_shell
    from src.general_settings_process import render_general_settings_process
    from src.quotes_process import render_process_quotes

    app_shell.FUNCTIONAL_MODULES["Cotizaciones"] = render_process_quotes
    app_shell.FUNCTIONAL_MODULES["Configuración General"] = render_general_settings_process
