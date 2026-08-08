"""Repositorio persistente para datos núcleo de CopyMary ERP.

Mantiene compatibilidad con las estructuras actuales basadas en listas y
configuración serializada, usando PostgreSQL cuando COPYMARY_DATABASE_URL está
configurada y SQLite en caso contrario.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from typing import Any

from src.erp_database import connect, database_url, initialize_database
from src.session_utils import now_iso

CORE_LIST_KEYS = frozenset(
    {
        "customers_registry",
        "sales_registry",
        "products_registry",
        "inventory_registry",
        "inventory_movements",
        "purchases_registry",
    }
)
CORE_ENTITY_KEYS = frozenset({"general_settings", *CORE_LIST_KEYS})

_INITIALIZED_DATABASES: set[str] = set()


def _ensure_database_initialized() -> None:
    """Inicializa el esquema una sola vez por destino de base de datos.

    Las lecturas núcleo ocurren varias veces durante el arranque. Ejecutar todas
    las migraciones antes de cada consulta hacía que la pantalla permaneciera
    cargando innecesariamente y podía agravar bloqueos de PostgreSQL. El destino
    puede cambiar durante el mismo proceso (por ejemplo, al cargar Secrets o en
    pruebas), así que la caché se mantiene por URL/ruta resuelta y no por proceso.
    """
    target = database_url()
    if target in _INITIALIZED_DATABASES:
        return
    initialize_database()
    _INITIALIZED_DATABASES.add(target)


def serialize_entity(value: object) -> object:
    """Convierte dataclasses y colecciones a una estructura JSON compatible."""
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [serialize_entity(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_entity(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_entity(item) for key, item in value.items()}
    return value


def save_entity(key: str, value: object) -> None:
    """Guarda una entidad completa mediante upsert, sin borrar otras entidades."""
    if key not in CORE_ENTITY_KEYS:
        raise ValueError(f"La entidad '{key}' no está habilitada para persistencia núcleo.")
    _ensure_database_initialized()
    payload = json.dumps(serialize_entity(value), ensure_ascii=False, sort_keys=True, default=str)
    updated_at = now_iso()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO core_entities(entity_key, payload_json, updated_at_utc)
            VALUES (?, ?, ?)
            ON CONFLICT(entity_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                updated_at_utc = excluded.updated_at_utc
            """,
            (key, payload, updated_at),
        )


def load_entity(key: str) -> object | None:
    """Lee una entidad persistida o devuelve None cuando todavía no existe."""
    if key not in CORE_ENTITY_KEYS:
        raise ValueError(f"La entidad '{key}' no está habilitada para persistencia núcleo.")
    _ensure_database_initialized()
    with connect() as connection:
        row = connection.execute(
            "SELECT payload_json FROM core_entities WHERE entity_key = ?",
            (key,),
        ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Los datos persistidos de '{key}' no contienen JSON válido.") from exc


def entity_exists(key: str) -> bool:
    """Indica si la entidad ya tiene un valor persistido."""
    if key not in CORE_ENTITY_KEYS:
        raise ValueError(f"La entidad '{key}' no está habilitada para persistencia núcleo.")
    _ensure_database_initialized()
    with connect() as connection:
        row = connection.execute(
            "SELECT 1 AS found FROM core_entities WHERE entity_key = ? LIMIT 1",
            (key,),
        ).fetchone()
    return row is not None


def migrate_entity_if_missing(key: str, value: object) -> bool:
    """Migra una entidad solo cuando la base aún no contiene esa clave."""
    if entity_exists(key):
        return False
    if value is None:
        return False
    if key in CORE_LIST_KEYS and not isinstance(value, list):
        raise ValueError(f"La entidad '{key}' debe migrarse como lista.")
    save_entity(key, value)
    return True


def load_list(key: str) -> list[dict[str, Any]] | None:
    """Lee una colección núcleo validando su estructura."""
    if key not in CORE_LIST_KEYS:
        raise ValueError(f"La entidad '{key}' no es una colección núcleo.")
    value = load_entity(key)
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"La entidad persistida '{key}' debe contener una lista de objetos.")
    return [dict(item) for item in value]
