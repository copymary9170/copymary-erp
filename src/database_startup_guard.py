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


def install_database_startup_guard() -> None:
    """Hace idempotente la inicialización y limita conexiones bloqueadas."""
    global _INSTALLED
    if _INSTALLED:
        return

    _install_postgres_timeout()

    from src import erp_database

    original_initialize = erp_database.initialize_database
    if not getattr(original_initialize, "_copymary_startup_guard", False):
        cached_initialize = lru_cache(maxsize=1)(original_initialize)
        cached_initialize._copymary_startup_guard = True  # type: ignore[attr-defined]
        erp_database.initialize_database = cached_initialize

    _INSTALLED = True
