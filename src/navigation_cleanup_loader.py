"""Limpieza defensiva de accesos duplicados en la navegación visible."""

from __future__ import annotations

from src import app_shell


_REMOVED_MENU_PAGES = {"Catálogo de artículos", "Recepción de mercancía"}
_REDIRECTS = {
    "Catálogo de artículos": "Inventario",
    "Recepción de mercancía": "Compras",
}


def activate_navigation_cleanup() -> None:
    """Elimina alias visibles aunque otra integración los vuelva a registrar."""
    try:
        from src import top_navigation_app
    except ImportError:
        return

    for area, config in tuple(top_navigation_app.SPECIALTY_AREAS.items()):
        icon, eyebrow, description, pages = config
        cleaned_pages = tuple(page for page in pages if page not in _REMOVED_MENU_PAGES)
        top_navigation_app.SPECIALTY_AREAS[area] = (icon, eyebrow, description, cleaned_pages)

    for page in _REMOVED_MENU_PAGES:
        top_navigation_app.DESCRIPTIONS.pop(page, None)

    aliases = getattr(top_navigation_app, "FUNCTIONAL_PAGE_ALIASES", {})
    aliases.update(_REDIRECTS)
    top_navigation_app.FUNCTIONAL_PAGE_ALIASES = aliases

    for page in _REMOVED_MENU_PAGES:
        app_shell.FUNCTIONAL_MODULES.pop(page, None)

    selected = app_shell.st.session_state.get("navigation_page")
    if selected in _REDIRECTS:
        app_shell.st.session_state["navigation_page"] = _REDIRECTS[selected]
