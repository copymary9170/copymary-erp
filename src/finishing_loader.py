"""Registro de los módulos de acabado (Plastificado, Corte en Cameo, Sublimación).

Sigue el mismo patrón que `print_cost_loader.py`: registra el renderer en
`app_shell.FUNCTIONAL_MODULES`, agrega la página a la navegación de
"Productos e inventario" y a la especialidad "Producción" en la navegación
superior.
"""

from src import app_shell
from src.finishing_cutting_cameo import render_finishing_cutting_cameo
from src.finishing_laminating import render_finishing_laminating
from src.finishing_sublimation import render_finishing_sublimation

MODULES = (
    ("Plastificado", render_finishing_laminating, "Descuenta laminado/bolsa de Inventario y suma uso de la plastificadora."),
    ("Corte en Cameo", render_finishing_cutting_cameo, "Descuenta vinil/sticker de Inventario y suma uso de la Silhouette Cameo."),
    ("Sublimado", render_finishing_sublimation, "Cotiza sublimación, valida blancos y consumibles de Inventario, controla parámetros, prensa y calidad."),
)


def activate_finishing_modules() -> None:
    pages = list(app_shell.NAVIGATION_GROUPS.get("Productos e inventario", ()))
    changed = False
    insert_at = pages.index("Análisis y costeo de impresión") + 1 if "Análisis y costeo de impresión" in pages else len(pages)
    for name, renderer, _description in MODULES:
        app_shell.FUNCTIONAL_MODULES[name] = renderer
        if name not in pages:
            pages.insert(insert_at, name)
            insert_at += 1
            changed = True
    if changed:
        app_shell.NAVIGATION_GROUPS["Productos e inventario"] = tuple(pages)

    try:
        from src import top_navigation_app
        icon, eyebrow, description, production_pages = top_navigation_app.SPECIALTY_AREAS["Producción"]
        new_pages = tuple(production_pages)
        for name, _renderer, _description in MODULES:
            if name not in new_pages:
                new_pages = (*new_pages, name)
        if new_pages != tuple(production_pages):
            top_navigation_app.SPECIALTY_AREAS["Producción"] = (icon, eyebrow, description, new_pages)
        for name, _renderer, description in MODULES:
            top_navigation_app.DESCRIPTIONS[name] = description
    except (ImportError, KeyError):
        pass
