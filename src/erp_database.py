"""Fundación de base de datos para CopyMary ERP.

Motor SQLite (por defecto, sin dependencias externas):
- Usa `COPYMARY_DB_PATH` o `copymary_erp.sqlite3`.

Motor PostgreSQL (producción, multiusuario):
- Se activa poniendo `COPYMARY_DATABASE_URL` con una URL `postgres://` o
  `postgresql://`. Requiere el driver `psycopg` (ver `requirements-postgres.txt`,
  no incluido en `requirements.txt` para mantener la instalación por defecto
  liviana).
- Todo el resto del código (`auth.py`, `bom_costing.py`, `bom_multilevel.py`,
  `exchange_rates.py`) sigue escribiendo SQL con placeholders `?` como si
  fuera SQLite: `_PostgresConnection` (más abajo) traduce automáticamente al
  dialecto de PostgreSQL, así que no hace falta tocar esos módulos.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterator
from uuid import uuid4

from src.session_utils import now_iso as _now


DEFAULT_SQLITE_PATH = "copymary_erp.sqlite3"
SCHEMA_VERSION = 4


@dataclass(frozen=True)
class DatabaseStatus:
    engine: str
    location: str
    schema_version: int
    ready: bool
    message: str


def database_url() -> str:
    """Devuelve la ubicación configurada de datos persistentes."""
    return os.getenv("COPYMARY_DATABASE_URL") or os.getenv("COPYMARY_DB_PATH") or DEFAULT_SQLITE_PATH


def is_sqlite_url(url: str) -> bool:
    return not url.startswith(("postgres://", "postgresql://"))


def sqlite_path(url: str | None = None) -> Path:
    raw = url or database_url()
    if raw.startswith("sqlite:///"):
        raw = raw.replace("sqlite:///", "", 1)
    return Path(raw)


def _translate_sql_for_postgres(sql: str) -> str:
    """Traduce sintaxis específica de SQLite al dialecto de PostgreSQL.

    Cubre exactamente lo que usa este código base hoy (verificado por
    búsqueda en todo `src/`): placeholders `?` y `INSERT OR IGNORE`. Si en el
    futuro se agrega otra sintaxis específica de SQLite en algún módulo,
    debe traducirse aquí también.
    """
    translated = sql.replace("?", "%s")
    if "INSERT OR IGNORE INTO" in translated:
        translated = translated.replace("INSERT OR IGNORE INTO", "INSERT INTO").rstrip()
        if "ON CONFLICT" not in translated.upper():
            translated += " ON CONFLICT DO NOTHING"
    return translated


class _PostgresConnection:
    """Adapta una conexión `psycopg` a la interfaz de `sqlite3.Connection`
    que ya usa el resto del código (`execute`, `executescript`, `commit`,
    `close`, placeholders `?`), para no tener que reescribir cada módulo que
    hace SQL directo.
    """

    def __init__(self, raw_connection: Any) -> None:
        self._raw = raw_connection

    def execute(self, sql: str, params: tuple = ()) -> Any:
        return self._raw.execute(_translate_sql_for_postgres(sql), params)

    def executescript(self, script: str) -> None:
        # Suficiente para el esquema de este proyecto: sentencias CREATE TABLE
        # simples, sin ';' dentro de literales de texto.
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self._raw.execute(statement)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()


@contextmanager
def connect() -> Iterator[Any]:
    """Abre conexión a la base configurada (SQLite por defecto, o PostgreSQL
    si `COPYMARY_DATABASE_URL` apunta a uno)."""
    url = database_url()

    if is_sqlite_url(url):
        path = sqlite_path(url)
        if path.parent and str(path.parent) not in {"", "."}:
            path.parent.mkdir(parents=True, exist_ok=True)
        connection: Any = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()
        return

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "COPYMARY_DATABASE_URL apunta a PostgreSQL, pero falta el driver "
            "'psycopg'. Instala con: pip install -r requirements-postgres.txt"
        ) from exc

    raw_connection = psycopg.connect(url, row_factory=dict_row)
    connection = _PostgresConnection(raw_connection)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _existing_columns(connection: Any, table_name: str) -> set[str]:
    if isinstance(connection, _PostgresConnection):
        rows = connection.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return {row["column_name"] for row in rows}
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _ensure_columns(connection: Any, table_name: str, columns: dict[str, str]) -> None:
    """Agrega columnas nuevas a una tabla existente sin perder datos (migración idempotente)."""
    present = _existing_columns(connection, table_name)
    for column_name, column_definition in columns.items():
        if column_name not in present:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _migrate_costing_v2(connection: Any) -> None:
    """Migración v2: color/BN, consumibles, sublimación, anidado, versiones y tasas."""
    _ensure_columns(connection, "production_materials", {"unit_cost_color": "REAL", "unit_cost_bw": "REAL"})
    _ensure_columns(connection, "machine_consumables", {"recommended_material_type": "TEXT NOT NULL DEFAULT ''"})
    _ensure_columns(connection, "product_recipes", {"version": "INTEGER NOT NULL DEFAULT 1", "parent_recipe_id": "TEXT"})
    _ensure_columns(
        connection,
        "recipe_steps",
        {
            "print_mode": "TEXT NOT NULL DEFAULT 'color'",
            "substrate": "TEXT NOT NULL DEFAULT ''",
            "temperature_c": "REAL",
            "time_seconds": "REAL",
            "pressure_level": "TEXT NOT NULL DEFAULT ''",
            "design_area_cm2": "REAL",
            "sheet_area_cm2": "REAL",
            "pieces_per_sheet": "REAL NOT NULL DEFAULT 1",
        },
    )
    _ensure_columns(connection, "costed_jobs", {"exchange_rate_id": "TEXT"})


def _migrate_auth_v3(connection: Any) -> None:
    """Migración v3: enlaza cada usuario con un rol."""
    _ensure_columns(connection, "app_users", {"role_id": "TEXT"})


def _migrate_resale_pricing_v4(connection: Any) -> None:
    """Migración v4: margen de reventa para materiales con use_type reventa/mixto.

    Antes, un material marcado como "reventa" (se vende tal cual, sin pasar por
    una receta de producción) no tenía forma de calcular su precio de venta:
    solo existían campos de costo. Este campo permite definir un margen propio
    para esos materiales, independiente del margen de las recetas.
    """
    _ensure_columns(connection, "production_materials", {"resale_margin_percent": "REAL NOT NULL DEFAULT 0"})


def initialize_database() -> DatabaseStatus:
    """Crea tablas fundacionales idempotentes."""
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS app_users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS app_roles (
                role_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS app_permissions (
                permission_id TEXT PRIMARY KEY,
                role_id TEXT NOT NULL,
                module_name TEXT NOT NULL,
                action_name TEXT NOT NULL,
                allowed INTEGER NOT NULL DEFAULT 1,
                created_at_utc TEXT NOT NULL,
                UNIQUE(role_id, module_name, action_name)
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                actor_user_id TEXT,
                module_name TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                action_name TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT,
                reason TEXT NOT NULL DEFAULT '',
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS exchange_rates (
                rate_id TEXT PRIMARY KEY,
                rate_date TEXT NOT NULL,
                source_currency TEXT NOT NULL,
                target_currency TEXT NOT NULL,
                rate REAL NOT NULL,
                source_name TEXT NOT NULL DEFAULT 'Manual',
                notes TEXT NOT NULL DEFAULT '',
                created_at_utc TEXT NOT NULL,
                UNIQUE(rate_date, source_currency, target_currency, source_name)
            );

            CREATE TABLE IF NOT EXISTS production_materials (
                material_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit TEXT NOT NULL,
                unit_cost REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                waste_percent REAL NOT NULL DEFAULT 0,
                use_type TEXT NOT NULL DEFAULT 'insumo',
                active INTEGER NOT NULL DEFAULT 1,
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS production_machines (
                machine_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                acquisition_cost REAL NOT NULL DEFAULT 0,
                useful_life_hours REAL NOT NULL DEFAULT 1,
                power_kw REAL NOT NULL DEFAULT 0,
                maintenance_cost_per_hour REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS machine_consumables (
                consumable_id TEXT PRIMARY KEY,
                machine_id TEXT NOT NULL,
                name TEXT NOT NULL,
                unit TEXT NOT NULL,
                replacement_cost REAL NOT NULL,
                useful_life_units REAL NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1,
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS product_recipes (
                recipe_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                target_margin_percent REAL NOT NULL DEFAULT 40,
                active INTEGER NOT NULL DEFAULT 1,
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recipe_steps (
                step_id TEXT PRIMARY KEY,
                recipe_id TEXT NOT NULL,
                step_order INTEGER NOT NULL,
                process_type TEXT NOT NULL,
                material_id TEXT,
                material_quantity REAL NOT NULL DEFAULT 0,
                machine_id TEXT,
                machine_minutes REAL NOT NULL DEFAULT 0,
                labor_minutes REAL NOT NULL DEFAULT 0,
                labor_rate_per_hour REAL NOT NULL DEFAULT 0,
                electricity_rate_per_kwh REAL NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS costed_jobs (
                job_id TEXT PRIMARY KEY,
                recipe_id TEXT NOT NULL,
                job_date TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 1,
                currency TEXT NOT NULL DEFAULT 'USD',
                cost_total REAL NOT NULL,
                price_total REAL NOT NULL,
                details_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at_utc) VALUES (?, ?, ?)",
            (1, "foundation_schema", _now()),
        )
        _migrate_costing_v2(connection)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at_utc) VALUES (?, ?, ?)",
            (2, "costing_process_detail", _now()),
        )
        _migrate_auth_v3(connection)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at_utc) VALUES (?, ?, ?)",
            (3, "auth_roles", _now()),
        )
        _migrate_resale_pricing_v4(connection)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at_utc) VALUES (?, ?, ?)",
            (4, "resale_pricing", _now()),
        )
    return get_database_status()


def get_database_status() -> DatabaseStatus:
    url = database_url()
    if not is_sqlite_url(url):
        try:
            with connect() as connection:
                row = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
                version = int(row["version"] or 0) if row and row["version"] is not None else 0
        except Exception as exc:  # noqa: BLE001 - se reporta como estado, no se relanza
            return DatabaseStatus("postgresql", url, 0, False, f"No se pudo conectar a PostgreSQL: {exc}")
        ready = version >= SCHEMA_VERSION
        message = "Base PostgreSQL lista." if ready else "PostgreSQL conectado; falta inicializar el esquema."
        return DatabaseStatus("postgresql", url, version, ready, message)
    path = sqlite_path(url)
    ready = path.exists()
    version = 0
    if ready:
        try:
            with connect() as connection:
                row = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
                version = int(row["version"] or 0) if row else 0
        except sqlite3.Error:
            return DatabaseStatus("sqlite", str(path), 0, False, "Existe archivo SQLite, pero el esquema no está inicializado.")
    return DatabaseStatus("sqlite", str(path), version, ready and version >= SCHEMA_VERSION, "Base inicial lista." if ready and version >= SCHEMA_VERSION else "Pendiente por inicializar.")


def latest_exchange_rate(target_currency: str, source_currency: str = "USD") -> dict[str, Any] | None:
    """Devuelve la tasa de cambio más reciente para source_currency -> target_currency."""
    initialize_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM exchange_rates
            WHERE source_currency = ? AND target_currency = ?
            ORDER BY rate_date DESC, created_at_utc DESC
            LIMIT 1
            """,
            (source_currency, target_currency),
        ).fetchone()
    return dict(row) if row else None


def record_audit_event(module_name: str, entity_name: str, entity_id: str, action_name: str, before: dict[str, Any] | None = None, after: dict[str, Any] | None = None, reason: str = "", actor_user_id: str = "") -> str:
    """Guarda un evento de auditoría en la base fundacional."""
    initialize_database()
    event_id = f"AUD-{uuid4().hex[:10].upper()}"
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_events(event_id, actor_user_id, module_name, entity_name, entity_id, action_name, before_json, after_json, reason, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                actor_user_id or None,
                module_name,
                entity_name,
                entity_id,
                action_name,
                json.dumps(before or {}, ensure_ascii=False, sort_keys=True),
                json.dumps(after or {}, ensure_ascii=False, sort_keys=True),
                reason,
                _now(),
            ),
        )
    return event_id
