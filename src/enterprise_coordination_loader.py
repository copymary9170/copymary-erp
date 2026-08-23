"""Registra coordinación transversal y simplifica la navegación del ERP."""
from __future__ import annotations

from src.enterprise_coordination_hub import (
    render_agenda_tasks,
    render_documents_center,
    render_management_overview,
    render_notification_center,
)


def activate_enterprise_coordination_hub() -> None:
    from src import app_shell, top_navigation_app

    app_shell.FUNCTIONAL_MODULES["Agenda y tareas"] = render_agenda_tasks
    app_shell.FUNCTIONAL_MODULES["Centro de notificaciones"] = render_notification_center
    app_shell.FUNCTIONAL_MODULES["Documentos y archivos"] = render_documents_center
    app_shell.FUNCTIONAL_MODULES["Resumen gerencial"] = render_management_overview

    # Nueva área transversal, evitando duplicar módulos transaccionales ya existentes.
    top_navigation_app.SPECIALTY_AREAS["Organización y seguimiento"] = (
        "▣", "Coordinación transversal",
        "Agenda, alertas y documentos que conectan todas las áreas del ERP.",
        ("Agenda y tareas", "Centro de notificaciones", "Documentos y archivos"),
    )
    for page, description in {
        "Agenda y tareas": "Calendario operativo, responsables, fechas límite y recordatorios.",
        "Centro de notificaciones": "Alertas unificadas de tareas, documentos, marketing, cobros, compras e inventario.",
        "Documentos y archivos": "Índice de documentos, enlaces, responsables y vencimientos.",
        "Resumen gerencial": "Vista transversal de pendientes y señales operativas.",
    }.items():
        top_navigation_app.DESCRIPTIONS[page] = description

    # El resumen gerencial complementa Reportes sin duplicar el centro existente.
    area = "Contabilidad y análisis"
    icon, eyebrow, description, pages = top_navigation_app.SPECIALTY_AREAS[area]
    if "Resumen gerencial" not in pages:
        top_navigation_app.SPECIALTY_AREAS[area] = (icon, eyebrow, description, (*pages, "Resumen gerencial"))

    # Respaldos deja de parecer un departamento independiente y pasa a gobierno del sistema.
    backup = top_navigation_app.SPECIALTY_AREAS.pop("Respaldos", None)
    if backup:
        _icon, _eyebrow, _description, backup_pages = backup
        area = "Administración y seguridad"
        icon, eyebrow, description, pages = top_navigation_app.SPECIALTY_AREAS[area]
        merged = tuple(dict.fromkeys((*pages, *backup_pages)))
        top_navigation_app.SPECIALTY_AREAS[area] = (icon, eyebrow, description, merged)

    # PAGE_TO_AREA se calculó al importar el shell; actualizamos solo las páginas tocadas.
    for page in ("Agenda y tareas", "Centro de notificaciones", "Documentos y archivos"):
        top_navigation_app.PAGE_TO_AREA[page] = "Organización y seguimiento"
    top_navigation_app.PAGE_TO_AREA["Resumen gerencial"] = "Contabilidad y análisis"
    for page in ("Respaldo general", "Respaldar activos"):
        top_navigation_app.PAGE_TO_AREA[page] = "Administración y seguridad"
