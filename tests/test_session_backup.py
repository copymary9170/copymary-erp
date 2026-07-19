"""Pruebas de `src/session_backup.py`: respaldo manual (archivo) y respaldo
automático en base de datos ("en la nube").
"""

from __future__ import annotations

import streamlit as st

from src import session_backup


# ---------------------------------------------------------------------------
# Respaldo manual (archivo) — round-trip básico
# ---------------------------------------------------------------------------

def test_build_and_parse_backup_roundtrip():
    st.session_state["customers_registry"] = [{"client_id": "C1", "name": "Ana"}]
    data = session_backup._build_backup()
    restored = session_backup._parse_backup(data)
    assert restored["customers_registry"] == [{"client_id": "C1", "name": "Ana"}]


def test_parse_backup_rejects_foreign_file():
    try:
        session_backup._parse_backup(b'{"application": "Otra cosa"}')
        assert False, "debia lanzar ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Respaldo automático en base de datos
# ---------------------------------------------------------------------------

def test_save_snapshot_to_database_returns_metadata(isolated_database):
    st.session_state["customers_registry"] = [{"client_id": "C1", "name": "Ana"}]
    saved = session_backup.save_snapshot_to_database()
    assert saved["snapshot_id"].startswith("SNAP-")
    assert saved["sections_included"] >= 1
    assert saved["size_bytes"] > 0


def test_latest_snapshot_info_none_when_nothing_saved(isolated_database):
    assert session_backup.latest_snapshot_info() is None


def test_latest_snapshot_info_reflects_most_recent_save(isolated_database):
    st.session_state["customers_registry"] = [{"client_id": "C1", "name": "Ana"}]
    session_backup.save_snapshot_to_database()
    info = session_backup.latest_snapshot_info()
    assert info is not None
    assert info["sections_included"] >= 1


def test_restore_latest_snapshot_from_database_brings_back_data(isolated_database):
    st.session_state["customers_registry"] = [{"client_id": "C1", "name": "Ana Pérez"}]
    session_backup.save_snapshot_to_database()

    st.session_state.clear()
    assert st.session_state.get("customers_registry") is None

    restored = session_backup.restore_latest_snapshot_from_database()
    assert restored is not None
    assert st.session_state["customers_registry"] == [{"client_id": "C1", "name": "Ana Pérez"}]


def test_restore_latest_snapshot_returns_none_when_nothing_saved(isolated_database):
    assert session_backup.restore_latest_snapshot_from_database() is None


def test_save_snapshot_prunes_old_ones_beyond_max(isolated_database, monkeypatch):
    monkeypatch.setattr(session_backup, "MAX_CLOUD_SNAPSHOTS", 3)
    for i in range(5):
        st.session_state["customers_registry"] = [{"client_id": f"C{i}"}]
        session_backup.save_snapshot_to_database()

    from src.erp_database import connect, initialize_database
    initialize_database()
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM session_snapshots").fetchone()["n"]
    assert count == 3


def test_save_snapshot_keeps_the_most_recent_ones_when_pruning(isolated_database, monkeypatch):
    monkeypatch.setattr(session_backup, "MAX_CLOUD_SNAPSHOTS", 2)
    for i in range(4):
        st.session_state["customers_registry"] = [{"client_id": f"C{i}"}]
        session_backup.save_snapshot_to_database()
    # El restaurado debe ser el ÚLTIMO guardado (C3), no uno viejo podado.
    st.session_state.clear()
    session_backup.restore_latest_snapshot_from_database()
    assert st.session_state["customers_registry"] == [{"client_id": "C3"}]


# ---------------------------------------------------------------------------
# session_has_data / restore_latest_snapshot_on_startup
# ---------------------------------------------------------------------------

def test_session_has_data_false_when_empty(isolated_database):
    assert session_backup.session_has_data() is False


def test_session_has_data_true_when_any_section_has_content(isolated_database):
    st.session_state["assets_registry"] = [{"asset_id": "AST-1"}]
    assert session_backup.session_has_data() is True


def test_restore_on_startup_does_nothing_when_session_already_has_data(isolated_database):
    """No debe pisar una sesión en uso, aunque haya un respaldo distinto guardado."""
    st.session_state["customers_registry"] = [{"client_id": "SAVED"}]
    session_backup.save_snapshot_to_database()

    st.session_state["customers_registry"] = [{"client_id": "EN_USO"}]
    session_backup.restore_latest_snapshot_on_startup()

    assert st.session_state["customers_registry"] == [{"client_id": "EN_USO"}]


def test_restore_on_startup_restores_when_session_is_empty(isolated_database):
    st.session_state["customers_registry"] = [{"client_id": "GUARDADO"}]
    session_backup.save_snapshot_to_database()

    st.session_state.clear()
    session_backup.restore_latest_snapshot_on_startup()

    assert st.session_state["customers_registry"] == [{"client_id": "GUARDADO"}]


def test_restore_on_startup_does_nothing_when_no_snapshot_exists(isolated_database):
    """Sesión vacía y sin ningún respaldo guardado: no debe fallar."""
    session_backup.restore_latest_snapshot_on_startup()
    assert st.session_state.get("customers_registry") is None


def test_restore_on_startup_swallows_database_errors(isolated_database, monkeypatch):
    """Un error de conexión (p. ej. Postgres caído) no debe impedir que la
    app arranque — se ignora en silencio."""
    def _boom():
        raise RuntimeError("sin conexión")

    monkeypatch.setattr(session_backup, "restore_latest_snapshot_from_database", _boom)
    session_backup.restore_latest_snapshot_on_startup()  # no debe lanzar
