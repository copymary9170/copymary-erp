"""Pruebas de gobierno para el centro de respaldos."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src import session_backup


def test_admin_has_all_backup_permissions(monkeypatch):
    monkeypatch.setattr(
        session_backup,
        "current_user",
        lambda: SimpleNamespace(user_id="USR-1", role_id="ROL-1", role_name="Administrador"),
    )
    for action in ("view", "create", "download", "restore"):
        assert session_backup.has_backup_permission(action) is True


def test_non_admin_is_deny_by_default(monkeypatch):
    monkeypatch.setattr(
        session_backup,
        "current_user",
        lambda: SimpleNamespace(user_id="USR-2", role_id="ROL-2", role_name="Operador"),
    )
    monkeypatch.setattr(session_backup, "permissions_for_role", lambda role_id: [])
    assert session_backup.has_backup_permission("restore") is False


def test_non_admin_requires_exact_action(monkeypatch):
    monkeypatch.setattr(
        session_backup,
        "current_user",
        lambda: SimpleNamespace(user_id="USR-2", role_id="ROL-2", role_name="Operador"),
    )
    monkeypatch.setattr(
        session_backup,
        "permissions_for_role",
        lambda role_id: [
            {"module_name": "backup", "action_name": "view", "allowed": 1},
            {"module_name": "backup", "action_name": "restore", "allowed": 0},
        ],
    )
    assert session_backup.has_backup_permission("view") is True
    assert session_backup.has_backup_permission("restore") is False
    assert session_backup.has_backup_permission("download") is False


def test_backup_health_red_without_snapshot():
    health = session_backup.backup_health(latest=None, is_durable=True)
    assert health["level"] == "red"
    assert health["label"] == "Riesgo"


def test_backup_health_yellow_when_sqlite_even_if_recent():
    latest = {"created_at_utc": datetime.now(timezone.utc).isoformat()}
    health = session_backup.backup_health(latest=latest, is_durable=False)
    assert health["level"] == "yellow"


def test_backup_health_green_for_recent_postgres_snapshot():
    latest = {"created_at_utc": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}
    health = session_backup.backup_health(latest=latest, is_durable=True)
    assert health["level"] == "green"
    assert health["label"] == "Protegido"


def test_backup_health_yellow_after_24_hours():
    latest = {"created_at_utc": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()}
    health = session_backup.backup_health(latest=latest, is_durable=True)
    assert health["level"] == "yellow"


def test_backup_health_red_after_seven_days():
    latest = {"created_at_utc": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()}
    health = session_backup.backup_health(latest=latest, is_durable=True)
    assert health["level"] == "red"


def test_restore_audits_rollback_snapshot(isolated_database, monkeypatch):
    import streamlit as st

    st.session_state["customers_registry"] = [{"client_id": "ORIGINAL"}]
    saved = session_backup.save_snapshot_to_database(audit=False)
    st.session_state["customers_registry"] = [{"client_id": "ACTUAL"}]

    calls = []
    monkeypatch.setattr(session_backup, "_audit", lambda action, snapshot_id="", **details: calls.append((action, snapshot_id, details)))

    session_backup.restore_snapshot_from_database(saved["snapshot_id"], create_rollback=True)

    assert st.session_state["customers_registry"] == [{"client_id": "ORIGINAL"}]
    assert calls
    action, snapshot_id, details = calls[-1]
    assert action == "restore"
    assert snapshot_id == saved["snapshot_id"]
    assert details["rollback_snapshot_id"].startswith("SNAP-")
