from datetime import datetime
import importlib
import sys
from types import SimpleNamespace

import pytest

from src import app_shell


def test_navigation_modules_import_without_cycle() -> None:
    sys.modules.pop("src.top_navigation_app", None)
    module = importlib.import_module("src.top_navigation_app")

    assert module.navigation_groups()["Comercial y CRM"]
    assert app_shell.navigation_groups()["Inventario y almacén"]


def test_new_navigation_pages_resolve_to_functional_renderers() -> None:
    from src import top_navigation_app

    assert top_navigation_app._functional_page_name("Recepción de mercancía") == "Compras"
    assert top_navigation_app._functional_page_name("Catálogo de artículos") == "Inventario"
    assert top_navigation_app._functional_page_name("Clientes") == "Clientes"
    assert top_navigation_app._functional_page_name("Recepción de mercancía") in app_shell.FUNCTIONAL_MODULES
    assert top_navigation_app._functional_page_name("Catálogo de artículos") in app_shell.FUNCTIONAL_MODULES


def test_alias_permissions_accept_visible_or_functional_name() -> None:
    from src import top_navigation_app

    assert top_navigation_app._page_is_allowed("Recepción de mercancía", {"Compras"})
    assert top_navigation_app._page_is_allowed("Recepción de mercancía", {"Recepción de mercancía"})
    assert top_navigation_app._page_is_allowed("Catálogo de artículos", {"Inventario"})
    assert not top_navigation_app._page_is_allowed("Catálogo de artículos", {"Compras"})
    assert top_navigation_app._page_is_allowed("Inicio", set())
    assert top_navigation_app._page_is_allowed("Cualquier módulo", None)


def test_effective_areas_show_alias_when_base_module_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    from src import top_navigation_app

    user = SimpleNamespace(role_id="ROL-1", role_name="Operador")
    monkeypatch.setattr(top_navigation_app.auth, "allowed_modules_for_role", lambda *_: {"Compras"})

    areas, allowed = top_navigation_app._effective_areas(user)

    assert allowed == {"Compras"}
    assert areas["Compras y abastecimiento"][3] == ("Compras", "Recepción de mercancía")


def test_home_shortcuts_are_filtered_by_permission() -> None:
    from src import top_navigation_app

    shortcuts = top_navigation_app._allowed_home_shortcuts(app_shell, {"Compras"})
    pages = tuple(shortcut[3] for shortcut in shortcuts)

    assert pages == ("Compras", "Recepción de mercancía")
    assert "Ventas y pedidos" not in pages
    assert "Respaldo general" not in pages


def test_home_shortcuts_allow_all_for_admin() -> None:
    from src import top_navigation_app

    assert top_navigation_app._allowed_home_shortcuts(app_shell, None) == app_shell._home_shortcuts()


def test_home_alerts_are_filtered_by_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    from src import top_navigation_app

    monkeypatch.setattr(app_shell, "_overdue_receivables", lambda: 2)
    monkeypatch.setattr(app_shell, "_pending_purchase_receipts", lambda: 3)
    monkeypatch.setattr(app_shell, "_inventory_alert_counts", lambda: (4, 5))

    alerts = top_navigation_app._allowed_home_alerts(app_shell, {"Compras"})

    assert alerts == (("Compras por recibir", 3, "Confirma mercancía pendiente de recepción.", "Compras y abastecimiento", "Recepción de mercancía"),)


@pytest.mark.parametrize(
    ("area", "page"),
    [
        ("Inicio", "Centro de control"),
        ("Comercial y CRM", "Ventas y pedidos"),
        ("Inventario y almacén", "Inventario"),
        ("Compras y abastecimiento", "Compras"),
        ("Finanzas y tesorería", "Panel financiero y cierres"),
        ("Respaldos", "Respaldo general"),
        ("Compras y abastecimiento", "Recepción de mercancía"),
        ("Inventario y almacén", "Catálogo de artículos"),
    ],
)
def test_home_shortcuts_use_active_navigation(area: str, page: str) -> None:
    assert app_shell._is_navigation_target(area, page)
    assert any(
        shortcut_area == area and shortcut_page == page
        for _, _, shortcut_area, shortcut_page in app_shell._home_shortcuts()
    )


def test_apply_pending_navigation_uses_active_taxonomy(monkeypatch: pytest.MonkeyPatch) -> None:
    session_state = {
        "pending_navigation_area": "Comercial y CRM",
        "pending_navigation_page": "Ventas y pedidos",
    }
    monkeypatch.setattr(app_shell.st, "session_state", session_state)

    app_shell._apply_pending_navigation()

    assert session_state["navigation_area"] == "Comercial y CRM"
    assert session_state["navigation_page"] == "Ventas y pedidos"


@pytest.mark.parametrize(
    ("hour", "expected"),
    [(0, "Buenos días"), (11, "Buenos días"), (12, "Buenas tardes"), (18, "Buenas tardes"), (19, "Buenas noches"), (23, "Buenas noches")],
)
def test_greeting_for_hour(hour: int, expected: str) -> None:
    assert app_shell._greeting_for_hour(hour) == expected


def test_home_greeting_uses_logged_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_shell.auth,
        "current_user",
        lambda: SimpleNamespace(display_name="María"),
    )

    assert app_shell._home_greeting(datetime(2026, 7, 26, 15, 0)) == "Buenas tardes, María"