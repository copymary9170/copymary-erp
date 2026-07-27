"""Pruebas de la persistencia genérica de secciones de sesión."""

from __future__ import annotations

import streamlit as st

from src.erp_database import connect
from src.general_settings import GeneralSettings
from src.general_settings_persistence import persist_general_settings_if_changed
from src.session_store import STARTUP_MARKER, hydrate_session_store_on_startup
from src.session_utils import read_dict, read_list, save_dict, save_list


def _settings() -> GeneralSettings:
    return GeneralSettings(
        business_name="Copy Mary",
        currency="VES",
        profit_margin=40.0,
        pricing_method="Margen sobre venta",
        monthly_internet=25.0,
        monthly_electricity=4.0,
        estimated_monthly_units=400,
        selected_asset_ids=(),
        bcv_rate=46.61,
        bcv_eur_rate=50.0,
        binance_rate=52.0,
        iva_rate=16.0,
        igtf_rate=3.0,
    )


def test_save_list_persists_and_lazy_read_recovers_after_reload():
    rows = [{"id": "LEAD-1", "name": "Cliente potencial"}]
    save_list("crm_leads", rows)

    st.session_state.clear()

    assert read_list("crm_leads") == rows
    assert st.session_state["crm_leads"] == rows


def test_save_dict_persists_and_recovers_after_reload():
    value = {"annual": {"target": 1000}}
    save_dict("business_goals", value)

    st.session_state.clear()

    assert read_dict("business_goals") == value


def test_general_settings_survives_reload_as_dataclass():
    st.session_state["general_settings"] = _settings()
    assert persist_general_settings_if_changed() is True

    st.session_state.clear()
    hydrate_session_store_on_startup()

    restored = st.session_state["general_settings"]
    assert isinstance(restored, GeneralSettings)
    assert restored.bcv_rate == 46.61
    assert restored.iva_rate == 16.0
    assert restored.igtf_rate == 3.0


def test_startup_hydration_never_overwrites_active_session_data():
    save_list("customers_registry", [{"id": "DB", "name": "Persistido"}])
    st.session_state.clear()
    st.session_state["customers_registry"] = [{"id": "LIVE", "name": "En uso"}]

    hydrate_session_store_on_startup()

    assert st.session_state["customers_registry"] == [{"id": "LIVE", "name": "En uso"}]


def test_database_failure_degrades_to_session_only(monkeypatch):
    import src.session_store as store

    monkeypatch.setattr(store, "ensure_session_store_table", lambda: False)
    rows = [{"id": "LOCAL"}]

    save_list("temporary_section", rows)

    assert st.session_state["temporary_section"] == rows
    assert read_list("temporary_section") == rows


def test_snapshot_style_migration_is_idempotent():
    # Se usa una sección conocida (registrada en SESSION_KEYS); solo esas pueden
    # provenir de un snapshot restaurado y por tanto migrarse al arrancar.
    legacy = [{"client_id": "C-1", "name": "Ana"}]
    st.session_state["customers_registry"] = legacy

    first = hydrate_session_store_on_startup()
    st.session_state.pop(STARTUP_MARKER, None)
    second = hydrate_session_store_on_startup()

    with connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM session_store WHERE section = ?",
            ("customers_registry",),
        ).fetchone()["count"]

    assert first["migrated"] >= 1
    assert second["migrated"] == 0
    assert count == 1
