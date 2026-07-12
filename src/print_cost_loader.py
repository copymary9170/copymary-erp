"""Registro del módulo de análisis y costeo de impresión."""
from src import app_shell
from src.print_cost_analyzer_v3 import render_print_cost_analyzer_v3


def activate_print_cost_module() -> None:
    name = "Análisis y costeo de impresión"
    app_shell.FUNCTIONAL_MODULES[name] = render_print_cost_analyzer_v3

    pages = list(app_shell.NAVIGATION_GROUPS.get("Productos e inventario", ()))
    if name not in pages:
        insert_at = pages.index("Costeo") if "Costeo" in pages else len(pages)
        pages.insert(insert_at, name)
        app_shell.NAVIGATION_GROUPS["Productos e inventario"] = tuple(pages)

    try:
        from src import top_navigation_app
        icon, eyebrow, description, production_pages = top_navigation_app.SPECIALTY_AREAS["Producción"]
        if name not in production_pages:
            top_navigation_app.SPECIALTY_AREAS["Producción"] = (
                icon,
                eyebrow,
                "Preprensa integrada con Activos, Inventario, Configuración y mantenimiento.",
                (name, *production_pages),
            )
        top_navigation_app.DESCRIPTIONS[name] = "Usa automáticamente impresoras, papel, desgaste y políticas del ERP."
    except (ImportError, KeyError):
        pass
