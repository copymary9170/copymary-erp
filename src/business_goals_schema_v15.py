"""Declaración de migración v15 para metas empresariales persistentes.

El esquema físico continúa siendo creado por ``ensure_goal_schema``. Este módulo
ofrece una entrada idempotente y un nombre estable para integrarlo en
``erp_database.initialize_database`` sin duplicar SQL ni cambiar módulos
operativos.
"""
from __future__ import annotations

from typing import Any

from src.business_goals_repository import ensure_goal_schema
from src.session_utils import now_iso

SCHEMA_VERSION = 15
MIGRATION_NAME = "persistent_business_goals"


def migrate_business_goals_v15(connection: Any | None = None) -> None:
    """Garantiza el esquema de metas y registra v15 cuando recibe conexión.

    ``connection`` es opcional para permitir despliegue progresivo. La inserción
    es idempotente y usa el adaptador SQL existente.
    """
    ensure_goal_schema()
    if connection is not None:
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at_utc) VALUES (?, ?, ?)",
            (SCHEMA_VERSION, MIGRATION_NAME, now_iso()),
        )
