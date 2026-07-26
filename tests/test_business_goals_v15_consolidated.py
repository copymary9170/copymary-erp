from __future__ import annotations

import importlib


def test_app_no_longer_imports_temporary_v15_bootstrap():
    source = importlib.import_module("pathlib").Path("app.py").read_text(encoding="utf-8")
    assert "business_goals_v15_bootstrap" not in source
    assert "activate_business_goals_schema_v15" not in source


def test_foundational_schema_version_is_v15_or_newer():
    from src import erp_database

    assert erp_database.SCHEMA_VERSION >= 15
