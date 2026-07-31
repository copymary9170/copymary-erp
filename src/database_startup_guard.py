"""Protecciones para evitar bloqueos durante el arranque del ERP."""

from __future__ import annotations

from functools import lru_cache
import os
from typing import Any


_INSTALLED = False


def _install_postgres_timeout() -> None:
    """Aplica un límite de espera a psycopg sin alterar la URL configurada."""
    try:
        import psycopg
    except ImportError:
        return

    original_connect = psycopg.connect
    if getattr(original_connect, "_copymary_timeout_guard", False):
        return

    default_timeout = max(int(os.getenv("COPYMARY_DB_CONNECT_TIMEOUT", "10")), 1)

    def connect_with_timeout(conninfo: str = "", *args: Any, **kwargs: Any):
        kwargs.setdefault("connect_timeout", default_timeout)
        return original_connect(conninfo, *args, **kwargs)

    connect_with_timeout._copymary_timeout_guard = True  # type: ignore[attr-defined]
    psycopg.connect = connect_with_timeout


def _schema_is_current(erp_database) -> bool:
    """Comprueba en la base si todas las migraciones ya fueron aplicadas."""
    try:
        with erp_database.connect() as connection:
            row = connection.execute(
                "SELECT MAX(version) AS version FROM schema_migrations"
            ).fetchone()
    except Exception:
        return False

    if not row:
        return False
    version = row["version"] if "version" in row.keys() else row[0]
    return int(version or 0) >= erp_database.SCHEMA_VERSION


def install_database_startup_guard() -> None:
    """Evita migraciones repetidas y limita conexiones bloqueadas."""
    global _INSTALLED
    if _INSTALLED:
        return

    _install_postgres_timeout()

    from src import erp_database

    original_initialize = erp_database.initialize_database
    if not getattr(original_initialize, "_copymary_startup_guard", False):

        @lru_cache(maxsize=1)
        def guarded_initialize():
            # Esta comprobación persiste entre recargas porque consulta la tabla
            # schema_migrations. Si el esquema ya está actualizado, no se vuelven
            # a ejecutar las 22 migraciones aunque Streamlit reinicie el proceso.
            if _schema_is_current(erp_database):
                return erp_database.get_database_status()
            return original_initialize()

        guarded_initialize._copymary_startup_guard = True  # type: ignore[attr-defined]
        erp_database.initialize_database = guarded_initialize

    _INSTALLED = True
