"""Fundación de base de datos para CopyMary ERP.

Este módulo no reemplaza todavía `st.session_state`; crea una capa inicial
segura para empezar la migración a datos persistentes sin romper la app actual.

Modo actual soportado sin dependencias externas:
- SQLite local/demo usando `COPYMARY_DB_PATH` o `copymary_erp.sqlite3`.

Modo objetivo documentado:
- PostgreSQL en producción mediante `COPYMARY_DATABASE_URL` cuando se agregue
  el driver correspondiente en una fase posterior.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterator
from uuid import uuid4


DEFAULT_SQLITE_PATH = "copymary_erp.sqlite3"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DatabaseStatus:
    engine: str
    location: str
    schema_version: int
    ready: bool
    message: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Abre conexión SQLite local/demo.

    PostgreSQL se deja explícitamente bloqueado hasta agregar driver, migraciones
    y variables de entorno en una fase posterior.
    """
    url = database_url()
    if not is_sqlite_url(url):
        raise RuntimeError("PostgreSQL está definido como objetivo, pero esta fase solo inicializa SQLite local/demo.")
    path = sqlite_path(url)
    if path.parent and str(path.parent) not in {"", "."}:
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


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
            (SCHEMA_VERSION, "foundation_schema", _now()),
        )
    return get_database_status()


def get_database_status() -> DatabaseStatus:
    url = database_url()
    if not is_sqlite_url(url):
        return DatabaseStatus("postgresql-target", url, 0, False, "PostgreSQL configurado como objetivo; falta activar driver/migraciones.")
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
