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
SCHEMA_VERSION = 22


@dataclass(frozen=True)
class DatabaseStatus:
    engine: str
    location: str
    schema_version: int
    ready: bool
    message: str


def _secret_database_url() -> str:
    try:
        import streamlit as st
        for key in ("COPYMARY_DATABASE_URL", "COPYMARY_DB_PATH"):
            if key in st.secrets:
                value = str(st.secrets[key]).strip()
                if value:
                    return value
    except Exception:
        pass
    return ""


def database_url() -> str:
    return (
        os.getenv("COPYMARY_DATABASE_URL")
        or os.getenv("COPYMARY_DB_PATH")
        or _secret_database_url()
        or DEFAULT_SQLITE_PATH
    )


def is_sqlite_url(url: str) -> bool:
    return not url.startswith(("postgres://", "postgresql://"))


def sqlite_path(url: str | None = None) -> Path:
    raw = url or database_url()
    if raw.startswith("sqlite:///"):
        raw = raw.replace("sqlite:///", "", 1)
    return Path(raw)


def _translate_sql_for_postgres(sql: str) -> str:
    translated = sql.replace("?", "%s")
    if "INSERT OR IGNORE INTO" in translated:
        translated = translated.replace("INSERT OR IGNORE INTO", "INSERT INTO").rstrip()
        if "ON CONFLICT" not in translated.upper():
            translated += " ON CONFLICT DO NOTHING"
    return translated


class _PostgresConnection:
    def __init__(self, raw_connection: Any) -> None:
        self._raw = raw_connection

    def execute(self, sql: str, params: tuple = ()) -> Any:
        return self._raw.execute(_translate_sql_for_postgres(sql), params)

    def executescript(self, script: str) -> None:
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
    except ImportError as exc:
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
    present = _existing_columns(connection, table_name)
    for column_name, column_definition in columns.items():
        if column_name not in present:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _migrate_costing_v2(connection: Any) -> None:
    _ensure_columns(connection, "production_materials", {"unit_cost_color": "REAL", "unit_cost_bw": "REAL"})
    _ensure_columns(connection, "machine_consumables", {"recommended_material_type": "TEXT NOT NULL DEFAULT ''"})
    _ensure_columns(connection, "product_recipes", {"version": "INTEGER NOT NULL DEFAULT 1", "parent_recipe_id": "TEXT"})
    _ensure_columns(connection, "recipe_steps", {"print_mode": "TEXT NOT NULL DEFAULT 'color'", "substrate": "TEXT NOT NULL DEFAULT ''", "temperature_c": "REAL", "time_seconds": "REAL", "pressure_level": "TEXT NOT NULL DEFAULT ''", "design_area_cm2": "REAL", "sheet_area_cm2": "REAL", "pieces_per_sheet": "REAL NOT NULL DEFAULT 1"})
    _ensure_columns(connection, "costed_jobs", {"exchange_rate_id": "TEXT"})


def _migrate_auth_v3(connection: Any) -> None:
    _ensure_columns(connection, "app_users", {"role_id": "TEXT"})


def _migrate_resale_pricing_v4(connection: Any) -> None:
    _ensure_columns(connection, "production_materials", {"resale_margin_percent": "REAL NOT NULL DEFAULT 0"})


def _migrate_login_lockout_v5(connection: Any) -> None:
    _ensure_columns(connection, "app_users", {"failed_login_count": "INTEGER NOT NULL DEFAULT 0", "locked_until": "TEXT"})


def _migrate_hr_payroll_v6(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS employees (employee_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, national_id TEXT NOT NULL DEFAULT '', position TEXT NOT NULL DEFAULT '', department TEXT NOT NULL DEFAULT '', hire_date TEXT NOT NULL, termination_date TEXT, status TEXT NOT NULL DEFAULT 'active', base_salary REAL NOT NULL DEFAULT 0, salary_currency TEXT NOT NULL DEFAULT 'USD', payment_frequency TEXT NOT NULL DEFAULT 'Mensual', bank_name TEXT NOT NULL DEFAULT '', bank_account TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', created_at_utc TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS payroll_periods (period_id TEXT PRIMARY KEY, period_start TEXT NOT NULL, period_end TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', closed_at_utc TEXT, created_at_utc TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS payroll_entries (entry_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, employee_id TEXT NOT NULL, base_salary REAL NOT NULL DEFAULT 0, bonuses_total REAL NOT NULL DEFAULT 0, bonuses_detail TEXT NOT NULL DEFAULT '', deductions_total REAL NOT NULL DEFAULT 0, deductions_detail TEXT NOT NULL DEFAULT '', currency TEXT NOT NULL DEFAULT 'USD', payment_status TEXT NOT NULL DEFAULT 'pending', paid_at_utc TEXT, created_at_utc TEXT NOT NULL, UNIQUE(period_id, employee_id));
    """)


def _migrate_maintenance_v7(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS maintenance_plans (plan_id TEXT PRIMARY KEY, machine_id TEXT NOT NULL, task_name TEXT NOT NULL, frequency_days INTEGER NOT NULL DEFAULT 30, last_done_date TEXT, next_due_date TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created_at_utc TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS maintenance_logs (log_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, machine_id TEXT NOT NULL, performed_date TEXT NOT NULL, performed_by TEXT NOT NULL DEFAULT '', cost REAL NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', created_at_utc TEXT NOT NULL);
    """)


def _migrate_quick_sale_v8(connection: Any) -> None:
    _ensure_columns(connection, "production_materials", {"quick_sale_price": "REAL NOT NULL DEFAULT 0"})


def _migrate_maintenance_usage_v9(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS maintenance_usage_logs (usage_id TEXT PRIMARY KEY, machine_id TEXT NOT NULL, usage_date TEXT NOT NULL, usage_hours REAL NOT NULL DEFAULT 0, source_module TEXT NOT NULL DEFAULT '', source_record_id TEXT NOT NULL DEFAULT '', created_at_utc TEXT NOT NULL);
    """)


def _migrate_maintenance_inventory_v10(connection: Any) -> None:
    _ensure_columns(connection, "maintenance_logs", {"inventory_movement_id": "TEXT"})


def _migrate_maintenance_spare_part_v11(connection: Any) -> None:
    _ensure_columns(connection, "maintenance_plans", {"spare_part_material_id": "TEXT", "spare_part_quantity": "REAL NOT NULL DEFAULT 0"})


def _migrate_payroll_cash_link_v12(connection: Any) -> None:
    _ensure_columns(connection, "payroll_entries", {"cash_movement_id": "TEXT"})


def _migrate_payroll_hr_v13(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS employee_salary_history (salary_history_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, effective_date TEXT NOT NULL, base_salary REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', reason TEXT NOT NULL DEFAULT '', created_at_utc TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS employee_time_off (time_off_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', notes TEXT NOT NULL DEFAULT '', created_at_utc TEXT NOT NULL);
    """)


def _migrate_session_snapshots_v14(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS session_snapshots (snapshot_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, snapshot_json TEXT NOT NULL, created_at_utc TEXT NOT NULL);
    """)


def _migrate_business_goals_v15(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS business_goals (id TEXT PRIMARY KEY, company_id TEXT NOT NULL DEFAULT 'default', kpi_code TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', target_value REAL NOT NULL, target_value_type TEXT NOT NULL DEFAULT 'number', period_type TEXT NOT NULL DEFAULT 'custom', start_date TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', scope_type TEXT NOT NULL DEFAULT 'company', scope_id TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL, updated_by TEXT NOT NULL, closed_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT, archived_at TEXT);
    CREATE TABLE IF NOT EXISTS goal_assignments (id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, assignee_type TEXT NOT NULL, assignee_id TEXT NOT NULL, weight REAL NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'active', assigned_by TEXT NOT NULL, assigned_at TEXT NOT NULL, UNIQUE(goal_id, assignee_type, assignee_id));
    CREATE TABLE IF NOT EXISTS goal_history (id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, goal_version INTEGER NOT NULL, change_type TEXT NOT NULL, field_name TEXT NOT NULL DEFAULT '', previous_value TEXT, new_value TEXT, reason TEXT NOT NULL DEFAULT '', changed_by TEXT NOT NULL, changed_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS goal_progress_snapshots (id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, measured_value REAL NOT NULL, progress_percentage REAL NOT NULL, calculated_status TEXT NOT NULL, measurement_period_start TEXT NOT NULL, measurement_period_end TEXT NOT NULL, measured_at TEXT NOT NULL, calculation_source TEXT NOT NULL DEFAULT '');
    CREATE INDEX IF NOT EXISTS idx_business_goals_scope ON business_goals(company_id, scope_type, scope_id, status);
    CREATE INDEX IF NOT EXISTS idx_business_goals_due ON business_goals(due_date, status);
    CREATE INDEX IF NOT EXISTS idx_goal_assignments_goal ON goal_assignments(goal_id, assignee_type, assignee_id);
    CREATE INDEX IF NOT EXISTS idx_goal_history_goal ON goal_history(goal_id, changed_at);
    CREATE INDEX IF NOT EXISTS idx_goal_snapshots_goal ON goal_progress_snapshots(goal_id, measured_at);
    """)


def _migrate_core_entities_v16(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS core_entities (
        entity_key TEXT PRIMARY KEY,
        payload_json TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL
    );
    """)


def _migrate_auth_schema_v17(connection: Any) -> None:
    roles_columns = _existing_columns(connection, "app_roles")
    if "role_name" in roles_columns and "name" not in roles_columns:
        connection.execute("ALTER TABLE app_roles RENAME COLUMN role_name TO name")
    _ensure_columns(connection, "app_roles", {"created_at_utc": "TEXT NOT NULL DEFAULT ''"})
    _ensure_columns(connection, "app_users", {"status": "TEXT NOT NULL DEFAULT 'active'"})
    _ensure_columns(connection, "app_permissions", {"permission_id": "TEXT", "created_at_utc": "TEXT NOT NULL DEFAULT ''"})


def _migrate_payroll_schema_v18(connection: Any) -> None:
    _ensure_columns(connection, "payroll_entries", {"payment_method": "TEXT NOT NULL DEFAULT ''"})
    off_columns = _existing_columns(connection, "employee_time_off")
    if "type" in off_columns and "leave_type" not in off_columns:
        connection.execute("ALTER TABLE employee_time_off RENAME COLUMN type TO leave_type")
    _ensure_columns(connection, "employee_time_off", {"days": "REAL NOT NULL DEFAULT 0", "paid": "INTEGER NOT NULL DEFAULT 0"})
    history_columns = _existing_columns(connection, "employee_salary_history")
    if "salary_history_id" in history_columns and "change_id" not in history_columns:
        connection.execute("ALTER TABLE employee_salary_history RENAME COLUMN salary_history_id TO change_id")
    if "base_salary" in history_columns and "new_salary" not in history_columns:
        connection.execute("ALTER TABLE employee_salary_history RENAME COLUMN base_salary TO new_salary")
    _ensure_columns(connection, "employee_salary_history", {"previous_salary": "REAL NOT NULL DEFAULT 0"})


def _migrate_production_machines_v19(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS production_machines (
        machine_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT '',
        acquisition_cost REAL NOT NULL DEFAULT 0,
        useful_life_hours REAL NOT NULL DEFAULT 0,
        power_kw REAL NOT NULL DEFAULT 0,
        maintenance_cost_per_hour REAL NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        created_at_utc TEXT NOT NULL DEFAULT ''
    );
    """)


def _migrate_maintenance_usage_columns_v20(connection: Any) -> None:
    _ensure_columns(connection, "maintenance_plans", {"usage_metric": "TEXT NOT NULL DEFAULT ''", "usage_frequency": "REAL NOT NULL DEFAULT 0", "last_done_usage": "REAL NOT NULL DEFAULT 0", "next_due_usage": "REAL NOT NULL DEFAULT 0", "current_usage": "REAL NOT NULL DEFAULT 0", "default_inventory_item_id": "TEXT NOT NULL DEFAULT ''"})
    _ensure_columns(connection, "maintenance_logs", {"usage_at_service": "REAL NOT NULL DEFAULT 0", "inventory_item_id": "TEXT NOT NULL DEFAULT ''", "inventory_quantity": "REAL NOT NULL DEFAULT 0", "inventory_deducted": "INTEGER NOT NULL DEFAULT 0"})


def _migrate_quick_service_prices_v21(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS quick_service_prices (
        service_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT '',
        unit_price REAL NOT NULL DEFAULT 0,
        unit_label TEXT NOT NULL DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1,
        created_at_utc TEXT NOT NULL DEFAULT ''
    );
    """)


def _migrate_missing_tables_v22(connection: Any) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS exchange_rates (
        rate_id TEXT PRIMARY KEY,
        rate_date TEXT NOT NULL,
        source_currency TEXT NOT NULL,
        target_currency TEXT NOT NULL,
        rate REAL NOT NULL DEFAULT 0,
        source_name TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at_utc TEXT NOT NULL DEFAULT ''
    );
    """)
    _ensure_columns(connection, "production_materials", {"currency": "TEXT NOT NULL DEFAULT 'USD'"})
    snapshot_columns = _existing_columns(connection, "session_snapshots")
    if snapshot_columns and ("user_id" in snapshot_columns or "snapshot_json" in snapshot_columns):
        source_json = "snapshot_json" if "snapshot_json" in snapshot_columns else "''"
        connection.executescript(f"""
        CREATE TABLE session_snapshots_new (
            snapshot_id TEXT PRIMARY KEY,
            data_json TEXT NOT NULL DEFAULT '',
            sections_included INTEGER NOT NULL DEFAULT 0,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            created_at_utc TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO session_snapshots_new(snapshot_id, data_json, created_at_utc)
            SELECT snapshot_id, COALESCE({source_json}, ''), created_at_utc FROM session_snapshots;
        DROP TABLE session_snapshots;
        ALTER TABLE session_snapshots_new RENAME TO session_snapshots;
        """)
    else:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS session_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            data_json TEXT NOT NULL DEFAULT '',
            sections_included INTEGER NOT NULL DEFAULT 0,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            created_at_utc TEXT NOT NULL DEFAULT ''
        );
        """)


def initialize_database() -> DatabaseStatus:
    with connect() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS app_users (user_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL, password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS app_roles (role_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '', created_at_utc TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS app_permissions (role_id TEXT NOT NULL, module_name TEXT NOT NULL, action_name TEXT NOT NULL, allowed INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(role_id, module_name, action_name));
        CREATE TABLE IF NOT EXISTS audit_events (event_id TEXT PRIMARY KEY, actor_user_id TEXT, module_name TEXT NOT NULL, entity_name TEXT NOT NULL, entity_id TEXT NOT NULL, action_name TEXT NOT NULL, before_json TEXT NOT NULL DEFAULT '{}', after_json TEXT NOT NULL DEFAULT '{}', reason TEXT NOT NULL DEFAULT '', created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS production_materials (material_id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, use_type TEXT NOT NULL DEFAULT 'produccion', unit TEXT NOT NULL DEFAULT 'unidad', unit_cost REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS machine_consumables (consumable_id TEXT PRIMARY KEY, machine_id TEXT NOT NULL, name TEXT NOT NULL, cost REAL NOT NULL DEFAULT 0, yield_units REAL NOT NULL DEFAULT 0, created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS product_recipes (recipe_id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, target_margin_percent REAL NOT NULL DEFAULT 40, active INTEGER NOT NULL DEFAULT 1, created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS recipe_steps (step_id TEXT PRIMARY KEY, recipe_id TEXT NOT NULL, step_order INTEGER NOT NULL, process_type TEXT NOT NULL, material_id TEXT, material_quantity REAL NOT NULL DEFAULT 0, machine_id TEXT, machine_minutes REAL NOT NULL DEFAULT 0, labor_minutes REAL NOT NULL DEFAULT 0, labor_rate_per_hour REAL NOT NULL DEFAULT 0, electricity_rate_per_kwh REAL NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS costed_jobs (job_id TEXT PRIMARY KEY, recipe_id TEXT NOT NULL, job_date TEXT NOT NULL, quantity REAL NOT NULL DEFAULT 1, currency TEXT NOT NULL DEFAULT 'USD', cost_total REAL NOT NULL, price_total REAL NOT NULL, details_json TEXT NOT NULL, created_at_utc TEXT NOT NULL);
        """)
        migrations = (
            (1, "foundation_schema", lambda: None),
            (2, "costing_process_detail", lambda: _migrate_costing_v2(connection)),
            (3, "auth_roles", lambda: _migrate_auth_v3(connection)),
            (4, "resale_pricing", lambda: _migrate_resale_pricing_v4(connection)),
            (5, "login_lockout", lambda: _migrate_login_lockout_v5(connection)),
            (6, "hr_payroll", lambda: _migrate_hr_payroll_v6(connection)),
            (7, "maintenance", lambda: _migrate_maintenance_v7(connection)),
            (8, "quick_sale_prices", lambda: _migrate_quick_sale_v8(connection)),
            (9, "maintenance_usage_triggers", lambda: _migrate_maintenance_usage_v9(connection)),
            (10, "maintenance_inventory_deduction", lambda: _migrate_maintenance_inventory_v10(connection)),
            (11, "maintenance_spare_part_planning", lambda: _migrate_maintenance_spare_part_v11(connection)),
            (12, "payroll_cash_link", lambda: _migrate_payroll_cash_link_v12(connection)),
            (13, "payroll_time_off_and_salary_history", lambda: _migrate_payroll_hr_v13(connection)),
            (14, "session_snapshots", lambda: _migrate_session_snapshots_v14(connection)),
            (15, "persistent_business_goals", lambda: _migrate_business_goals_v15(connection)),
            (16, "persistent_core_entities", lambda: _migrate_core_entities_v16(connection)),
            (17, "auth_schema_alignment", lambda: _migrate_auth_schema_v17(connection)),
            (18, "payroll_schema_alignment", lambda: _migrate_payroll_schema_v18(connection)),
            (19, "production_machines_table", lambda: _migrate_production_machines_v19(connection)),
            (20, "maintenance_usage_columns", lambda: _migrate_maintenance_usage_columns_v20(connection)),
            (21, "quick_service_prices_table", lambda: _migrate_quick_service_prices_v21(connection)),
            (22, "missing_tables_and_columns", lambda: _migrate_missing_tables_v22(connection)),
        )
        for version, name, migration in migrations:
            migration()
            connection.execute("INSERT OR IGNORE INTO schema_migrations(version, name, applied_at_utc) VALUES (?, ?, ?)", (version, name, _now()))
    return get_database_status()


def get_database_status() -> DatabaseStatus:
    url = database_url()
    if not is_sqlite_url(url):
        try:
            with connect() as connection:
                row = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
                version = int(row["version"] or 0) if row and row["version"] is not None else 0
        except Exception as exc:
            return DatabaseStatus("postgresql", url, 0, False, f"No se pudo conectar a PostgreSQL: {exc}")
        ready = version >= SCHEMA_VERSION
        return DatabaseStatus("postgresql", url, version, ready, "Base PostgreSQL lista." if ready else "PostgreSQL conectado; falta inicializar el esquema.")
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
    initialize_database()
    with connect() as connection:
        row = connection.execute("SELECT * FROM exchange_rates WHERE source_currency = ? AND target_currency = ? ORDER BY rate_date DESC, created_at_utc DESC LIMIT 1", (source_currency, target_currency)).fetchone()
    return dict(row) if row else None


def record_audit_event(module_name: str, entity_name: str, entity_id: str, action_name: str, before: dict[str, Any] | None = None, after: dict[str, Any] | None = None, reason: str = "", actor_user_id: str = "") -> str:
    initialize_database()
    event_id = f"AUD-{uuid4().hex[:10].upper()}"
    with connect() as connection:
        connection.execute("INSERT INTO audit_events(event_id, actor_user_id, module_name, entity_name, entity_id, action_name, before_json, after_json, reason, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (event_id, actor_user_id or None, module_name, entity_name, entity_id, action_name, json.dumps(before or {}, ensure_ascii=False, sort_keys=True), json.dumps(after or {}, ensure_ascii=False, sort_keys=True), reason, _now()))
    return event_id
