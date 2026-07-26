"""Activación controlada de la migración v15 de metas empresariales.

Este puente ejecuta primero las migraciones fundacionales existentes, crea el
esquema idempotente de metas y registra la versión 15. Se mantiene separado de
la interfaz y de los módulos operativos para que el despliegue sea reversible.
"""
from __future__ import annotations

from src import erp_database
from src.business_goals_schema_v15 import MIGRATION_NAME, SCHEMA_VERSION, migrate_business_goals_v15
from src.session_utils import now_iso


def activate_business_goals_schema_v15() -> None:
    """Garantiza y registra v15 antes de habilitar el gestor de metas."""
    erp_database.initialize_database()
    migrate_business_goals_v15()
    with erp_database.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at_utc) VALUES (?, ?, ?)",
            (SCHEMA_VERSION, MIGRATION_NAME, now_iso()),
        )
    # get_database_status consulta esta constante en tiempo de ejecución.
    # El ajuste se limita al proceso actual y conserva compatibilidad mientras
    # la migración se consolida directamente en erp_database.py.
    erp_database.SCHEMA_VERSION = max(erp_database.SCHEMA_VERSION, SCHEMA_VERSION)
