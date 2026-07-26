from datetime import datetime
from types import SimpleNamespace

import pytest

from src import app_shell


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
