"""Pruebas de `src/session_backup.py`: respaldo manual y snapshots versionados."""

from __future__ import annotations

import json

import streamlit as st

from src import session_backup


def test_build_and_parse_backup_roundtrip():
    st.session_state["customers_registry"] = [{"client_id": "C1", "name": "Ana"}]
    data = session_backup._build_backup()
    restored = session_backup._parse_backup(data)
    assert restored["customers_registry"] == [{"client_id": "C1", "name": "Ana"}]


def test_v3_backup_contains_valid_checksum():
    st.session_state["customers_registry"] = [{"client_id": "C1"}]
    payload = json.loads(session_backup._build_backup().decode("utf-8"))
    assert payload["backup_version"] == 3
    assert payload["checksum_sha256"] == session_backup._checksum(payload["data"])


def test_parse_backup_rejects_tampered_v3_file():
    st.session_state["customers_registry"] = [{"client_id": "C1"}]
    payload = json.loads(session_backup._build_backup().decode("utf-8"))
    payload["data"]["customers_registry"] = [{"client_id": "ALTERADO"}]
    try:
        session_backup._parse_backup(json.dumps(payload).encode("utf-8"))
        assert False, "debia lanzar ValueError"
    except ValueError as exc:
        assert "integridad" in str(exc).lower()


def test_parse_backup_rejects_foreign_file():
    try:
        session_backup._parse_backup(b'{"application": "Otra cosa"}')
        assert False, "debia lanzar ValueError"
    except ValueError:
        pass


def test_save_snapshot_to_database_returns_metadata(isolated_database):
    st.session_state["customers_registry"] = [{"client_id": "C1", "name": "Ana"}]
    saved = session_backup.save_snapshot_to_database()
    assert saved["snapshot_id"].startswith("SNAP-")
    assert saved["sections_included"] >= 1
    assert saved["size_bytes"] > 0
    assert len(saved["checksum_sha256"]) == 64


def test_latest_snapshot_info_none_when_nothing_saved(isolated_database):
    assert session_backup.latest_snapshot_info() is None


def test_latest_snapshot_info_reflects_most_recent_save(isolated_database):
    st.session_state["customers_registry"] = [{"client_id": "C1", "name": "Ana"}]
    session_backup.save_snapshot_to_database()
    info = session_backup.latest_snapshot_info()
    assert info is not None
    assert info["sections_included"] >= 1


def test_list_snapshots_returns_newest_first(isolated_database):
    for client_id in ("A", "B", "C"):
        st.session_state["customers_registry"] = [{"client_id": client_id}]
        session_backup.save_snapshot_to_database()
    rows = session_backup.list_snapshots()
    assert len(rows) == 3
    assert rows[0]["created_at_utc"] >= rows[-1]["created_at_utc"]


def test_snapshot_bytes_returns_downloadable_backup(isolated_database):
    st.session_state["customers_registry"] = [{"client_id": "C1"}]
    saved = session_backup.save_snapshot_to_database()
    raw = session_backup.snapshot_bytes(saved["snapshot_id"])
    assert raw is not None
    restored = session_backup._parse_backup(raw)
    assert restored["customers_registry"] == [{"client_id": "C1"}]


def test_restore_latest_snapshot_from_database_brings_back_data(isolated_database):
    st.session_state["customers_registry"] = [{"client_id": "C1", "name": "Ana Pérez"}]
    session_backup.save_snapshot_to_database()

    st.session_state.clear()
    assert st.session_state.get("customers_registry") is None

    restored = session_backup.restore_latest_snapshot_from_database()
    assert restored is not None
    assert st.session_state["customers_registry"] == [{"client_id": "C1", "name": "Ana Pérez"}]


def test_restore_specific_snapshot_creates_rollback(isolated_database):
    st.session_state["customers_registry"] = [{"client_id": "ANTERIOR"}]
    old = session_backup.save_snapshot_to_database()
    st.session_state["customers_registry"] = [{"client_id": "ACTUAL"}]

    before_count = len(session_backup.list_snapshots())
    session_backup.restore_snapshot_from_database(old["snapshot_id"], create_rollback=True)
    after_count = len(session_backup.list_snapshots())

    assert st.session_state["customers_registry"] == [{"client_id": "ANTERIOR"}]
    assert after_count == before_count + 1


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
    st.session_state.clear()
    session_backup.restore_latest_snapshot_from_database()
    assert st.session_state["customers_registry"] == [{"client_id": "C3"}]


def test_session_has_data_false_when_empty(isolated_database):
    assert session_backup.session_has_data() is False


def test_session_has_data_true_when_any_section_has_content(isolated_database):
    st.session_state["assets_registry"] = [{"asset_id": "AST-1"}]
    assert session_backup.session_has_data() is True


def test_restore_on_startup_does_nothing_when_session_already_has_data(isolated_database):
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
    session_backup.restore_latest_snapshot_on_startup()
    assert st.session_state.get("customers_registry") is None


def test_restore_on_startup_swallows_database_errors(isolated_database, monkeypatch):
    def _boom():
        raise RuntimeError("sin conexión")

    monkeypatch.setattr(session_backup, "_latest_snapshot_row", _boom)
    session_backup.restore_latest_snapshot_on_startup()
