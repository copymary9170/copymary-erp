"""Activa el Workspace unificado de Activos y consolida mantenimiento.

El mantenimiento preventivo conserva toda su funcionalidad, pero deja de
aparecer como una página paralela: se accede desde Activos > Mantenimiento
y garantías, donde convive con el resumen, historial y estado de garantías.
"""


def _consolidate_assets_navigation() -> None:
    """Evita dos entradas de menú para el mismo flujo de mantenimiento."""
    from src import top_navigation_app

    area = "Activos y mantenimiento"
    config = top_navigation_app.SPECIALTY_AREAS.get(area)
    if config:
        icon, title, _description, pages = config
        consolidated_pages = tuple(page for page in pages if page != "Mantenimiento preventivo")
        top_navigation_app.SPECIALTY_AREAS[area] = (
            icon,
            title,
            "Equipos, depreciación, mantenimiento, garantías, electricidad y reemplazo.",
            consolidated_pages,
        )

    top_navigation_app.DESCRIPTIONS["Activos"] = (
        "Workspace de equipos, ficha técnica, mantenimiento preventivo e historial, "
        "garantías, electricidad y reemplazo."
    )
    # Se conserva la descripción histórica por compatibilidad con enlaces o
    # permisos antiguos, aunque ya no se muestre como página independiente.
    top_navigation_app.DESCRIPTIONS["Mantenimiento preventivo"] = (
        "Integrado en Activos → Mantenimiento y garantías."
    )


def activate_assets_workspace() -> None:
    from src import app_shell
    from src.assets_workspace import render_assets_workspace

    # Una sola puerta de entrada. No se borra machine_maintenance ni sus datos:
    # assets_workspace lo sigue renderizando dentro de Mantenimiento y garantías.
    app_shell.FUNCTIONAL_MODULES["Activos"] = render_assets_workspace
    app_shell.FUNCTIONAL_MODULES.pop("Mantenimiento preventivo", None)
    _consolidate_assets_navigation()
