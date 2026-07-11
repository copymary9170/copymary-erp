"""Pruebas de la capa fundacional de base de datos (`src/erp_database.py`)."""

from __future__ import annotations

from src import erp_database as db


def test_initialize_database_creates_ready_schema(isolated_database):
    status = db.initialize_database()

    assert status.engine == "sqlite"
    assert status.ready is True
    assert status.schema_version == db.SCHEMA_VERSION


def test_initialize_database_is_idempotent(isolated_database):
    """Debe poder llamarse muchas veces sin fallar ni duplicar datos."""
    first = db.initialize_database()
    second = db.initialize_database()
    third = db.initialize_database()

    assert first.schema_version == second.schema_version == third.schema_version

    with db.connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"]
    # Una fila por migración (1, 2, 3), sin duplicados aunque se llame varias veces.
    assert count == db.SCHEMA_VERSION


def test_get_database_status_before_initialization_reports_not_ready(isolated_database):
    """Antes de crear el archivo, el estado debe indicar que falta inicializar."""
    status = db.get_database_status()
    assert status.ready is False


def test_migrations_add_expected_columns(isolated_database):
    db.initialize_database()
    with db.connect() as conn:
        columns = db._existing_columns(conn, "app_users")
        recipe_columns = db._existing_columns(conn, "recipe_steps")

    # Migración v3 (auth): cada usuario debe poder enlazarse a un rol.
    assert "role_id" in columns
    # Migración v2 (costeo): pasos de receta con datos de proceso de impresión.
    assert "print_mode" in recipe_columns
    assert "pieces_per_sheet" in recipe_columns


def test_record_audit_event_persists_before_and_after(isolated_database):
    event_id = db.record_audit_event(
        module_name="inventario",
        entity_name="production_materials",
        entity_id="MAT-0001",
        action_name="update",
        before={"unit_cost": 1.0},
        after={"unit_cost": 1.5},
        reason="ajuste de precio de proveedor",
        actor_user_id="USR-TEST",
    )

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM audit_events WHERE event_id = ?", (event_id,)).fetchone()

    assert row is not None
    assert row["module_name"] == "inventario"
    assert row["reason"] == "ajuste de precio de proveedor"
    assert '"unit_cost": 1.0' in row["before_json"]
    assert '"unit_cost": 1.5' in row["after_json"]


def test_latest_exchange_rate_returns_none_when_absent(isolated_database):
    assert db.latest_exchange_rate("VES") is None


def test_latest_exchange_rate_returns_most_recent(isolated_database):
    db.initialize_database()
    with db.connect() as conn:
        for rate_date, rate in (("2026-07-01", 36.0), ("2026-07-08", 40.5)):
            conn.execute(
                """
                INSERT INTO exchange_rates(rate_id, rate_date, source_currency, target_currency, rate, source_name, notes, created_at_utc)
                VALUES (?, ?, 'USD', 'VES', ?, 'Manual', '', ?)
                """,
                (f"RATE-{rate_date}", rate_date, rate, db._now()),
            )

    latest = db.latest_exchange_rate("VES")
    assert latest is not None
    assert latest["rate"] == 40.5
    assert latest["rate_date"] == "2026-07-08"
