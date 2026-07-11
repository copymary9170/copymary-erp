"""Pruebas de `erp_database.py` contra PostgreSQL real.

Se saltan automáticamente si no hay un PostgreSQL accesible (por ejemplo, en
una máquina de desarrollo sin el servidor instalado) — no son obligatorias
para correr `pytest tests/`, pero si `COPYMARY_TEST_POSTGRES_URL` está
definida, validan que el adaptador `_PostgresConnection` (traducción de `?` a
`%s`, `INSERT OR IGNORE` a `ON CONFLICT DO NOTHING`, `PRAGMA table_info` a
`information_schema`) funciona igual que en SQLite.

Para correrlas localmente:
    export COPYMARY_TEST_POSTGRES_URL="postgresql://user:pass@localhost:5432/copymary_test"
    pytest tests/test_erp_database_postgres.py -v
"""

from __future__ import annotations

import os

import pytest

POSTGRES_URL = os.environ.get("COPYMARY_TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="COPYMARY_TEST_POSTGRES_URL no está definida (se salta la prueba contra PostgreSQL real)",
)


@pytest.fixture(autouse=True)
def postgres_database(monkeypatch):
    """Apunta cada prueba a PostgreSQL y limpia las tablas después."""
    monkeypatch.setenv("COPYMARY_DATABASE_URL", POSTGRES_URL)
    monkeypatch.delenv("COPYMARY_DB_PATH", raising=False)
    yield
    # Limpieza: elimina todas las tablas conocidas para que la siguiente
    # prueba empiece de cero (más simple y explícito que un DROP DATABASE).
    from src import erp_database as db

    with db.connect() as conn:
        conn.execute(
            """
            DROP TABLE IF EXISTS
                schema_migrations, app_users, app_roles, app_permissions,
                audit_events, exchange_rates, production_materials,
                production_machines, machine_consumables, product_recipes,
                recipe_steps, costed_jobs, recipe_components, recipe_versions
            CASCADE
            """
        )


def test_initialize_database_creates_ready_schema_on_postgres():
    from src import erp_database as db

    status = db.initialize_database()
    assert status.engine == "postgresql"
    assert status.ready is True
    assert status.schema_version == db.SCHEMA_VERSION


def test_initialize_database_is_idempotent_on_postgres():
    """El mismo comportamiento que en SQLite: INSERT OR IGNORE -> ON CONFLICT DO NOTHING."""
    from src import erp_database as db

    db.initialize_database()
    db.initialize_database()
    db.initialize_database()

    with db.connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"]
    assert count == db.SCHEMA_VERSION


def test_ensure_columns_via_information_schema_on_postgres():
    """_existing_columns() debe leer information_schema en vez de PRAGMA."""
    from src import erp_database as db

    db.initialize_database()
    with db.connect() as conn:
        columns = db._existing_columns(conn, "app_users")
    assert "role_id" in columns  # agregado por la migración v3


def test_record_audit_event_on_postgres():
    from src import erp_database as db

    event_id = db.record_audit_event(
        module_name="inventario",
        entity_name="production_materials",
        entity_id="MAT-0001",
        action_name="update",
        before={"unit_cost": 1.0},
        after={"unit_cost": 1.5},
        reason="prueba contra PostgreSQL",
    )
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM audit_events WHERE event_id = ?", (event_id,)).fetchone()
    assert row["reason"] == "prueba contra PostgreSQL"


def test_auth_flow_on_postgres():
    """auth.py hace SQL directo: valida que el login funcione igual sobre PostgreSQL."""
    from src import auth

    role_id = auth.create_role(auth.ADMIN_ROLE_NAME)
    auth.create_user("admin@copymary.test", "Admin", "clave-larga-123", role_id)

    assert auth.authenticate("admin@copymary.test", "clave-larga-123") is True
    assert auth.authenticate("admin@copymary.test", "clave-incorrecta") is False


def test_bom_costing_recipe_total_on_postgres():
    """bom_costing.py hace SQL directo: valida el costeo de una receta real sobre PostgreSQL."""
    from src import erp_database as db
    from src import bom_costing

    db.initialize_database()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO production_materials(material_id, name, category, unit, unit_cost, currency, unit_cost_color, created_at_utc)
            VALUES (?, 'Material PG', 'insumo', 'unidad', 2.0, 'USD', 2.0, ?)
            """,
            ("MAT-PG", db._now()),
        )
        conn.execute(
            """
            INSERT INTO recipe_steps(step_id, recipe_id, step_order, process_type, material_id, material_quantity, created_at_utc)
            VALUES ('STP-PG', 'REC-PG', 1, 'Impresión', 'MAT-PG', 1.0, ?)
            """,
            (db._now(),),
        )

    total, details = bom_costing._recipe_total("REC-PG")
    assert total == 2.0
    assert len(details) == 1
