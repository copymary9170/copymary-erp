from __future__ import annotations

from src import erp_database


def test_initialize_database_consolidates_v15(tmp_path, monkeypatch):
    monkeypatch.setenv("COPYMARY_DB_PATH", str(tmp_path / "erp-v15.sqlite3"))

    status = erp_database.initialize_database()

    assert erp_database.SCHEMA_VERSION == 15
    assert status.ready is True
    assert status.schema_version >= 15

    with erp_database.connect() as connection:
        migration = connection.execute(
            "SELECT name FROM schema_migrations WHERE version = ?",
            (15,),
        ).fetchone()
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert migration["name"] == "persistent_business_goals"
    assert {
        "business_goals",
        "goal_assignments",
        "goal_history",
        "goal_progress_snapshots",
    }.issubset(tables)


def test_initialize_database_v15_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("COPYMARY_DB_PATH", str(tmp_path / "erp-v15-repeat.sqlite3"))

    first = erp_database.initialize_database()
    second = erp_database.initialize_database()

    assert first.ready is True
    assert second.ready is True
    assert second.schema_version >= 15

    with erp_database.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS total FROM schema_migrations WHERE version = ?",
            (15,),
        ).fetchone()

    assert int(count["total"]) == 1
