"""Pruebas de la restauración selectiva al iniciar la aplicación."""

from __future__ import annotations

import streamlit as st

from src.general_settings import GeneralSettings
from src import session_backup, startup_restore


def _settings(*, bcv_rate: float) -> GeneralSettings:
    return GeneralSettings(
        business_name="Copy Mary",
        currency="USD",
        profit_margin=40.0,
        pricing_method="Margen sobre costo",
        monthly_internet=25.0,
        monthly_electricity=4.0,
        estimated_monthly_units=400,
        selected_asset_ids=(),
        bcv_rate=bcv_rate,
    )


def test_startup_restores_general_settings_without_overwriting_other_data(isolated_database):
    st.session_state["general_settings"] = _settings(bcv_rate=150.0)
    st.session_state["customers_registry"] = [{"client_id": "GUARDADO"}]
    session_backup.save_snapshot_to_database()

    st.session_state.clear()
    st.session_state["general_settings"] = _settings(bcv_rate=0.0)
    st.session_state["customers_registry"] = [{"client_id": "EN_USO"}]

    startup_restore.restore_session_snapshot_on_startup()

    assert st.session_state["general_settings"].bcv_rate == 150.0
    assert st.session_state["customers_registry"] == [{"client_id": "EN_USO"}]


def test_startup_restore_runs_only_once_per_streamlit_session(isolated_database):
    st.session_state["general_settings"] = _settings(bcv_rate=150.0)
    session_backup.save_snapshot_to_database()

    st.session_state.clear()
    startup_restore.restore_session_snapshot_on_startup()
    st.session_state["general_settings"] = _settings(bcv_rate=200.0)

    startup_restore.restore_session_snapshot_on_startup()

    assert st.session_state["general_settings"].bcv_rate == 200.0


def test_startup_restores_all_sections_when_session_is_empty(isolated_database):
    st.session_state["general_settings"] = _settings(bcv_rate=150.0)
    st.session_state["customers_registry"] = [{"client_id": "GUARDADO"}]
    session_backup.save_snapshot_to_database()

    st.session_state.clear()
    startup_restore.restore_session_snapshot_on_startup()

    assert st.session_state["general_settings"].bcv_rate == 150.0
    assert st.session_state["customers_registry"] == [{"client_id": "GUARDADO"}]
