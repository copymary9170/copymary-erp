from __future__ import annotations

from datetime import date

from src.business_goals_admin import _date_text, _goal_options


def test_date_text_uses_iso_prefix():
    assert _date_text("2026-07-31T10:30:00") == "2026-07-31"


def test_date_text_uses_fallback():
    fallback = date(2026, 8, 1)
    assert _date_text("", fallback) == "2026-08-01"


def test_goal_options_keep_each_persistent_id():
    goals = [
        {"id": "GOL-1", "name": "Ventas", "status": "active"},
        {"id": "GOL-2", "name": "Ventas", "status": "paused"},
    ]
    options = _goal_options(goals)
    assert len(options) == 2
    assert {row["id"] for row in options.values()} == {"GOL-1", "GOL-2"}


def test_goal_options_show_readable_status():
    options = _goal_options([
        {"id": "GOL-1", "name": "Cobranza", "status": "closed"},
    ])
    label = next(iter(options))
    assert "Cerrada" in label
    assert "GOL-1" in label
