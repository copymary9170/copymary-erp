"""Activa el Workspace unificado de Activos sin eliminar módulos existentes."""


def activate_assets_workspace() -> None:
    from src import app_shell
    from src.assets_workspace import render_assets_workspace

    app_shell.FUNCTIONAL_MODULES["Activos"] = render_assets_workspace
