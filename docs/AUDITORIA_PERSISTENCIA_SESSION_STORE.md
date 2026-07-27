# Auditoría P0 — persistencia viva de `st.session_state`

## Estado encontrado

La aplicación ya tenía dos mecanismos parciales:

1. `session_snapshots`: respaldo manual/histórico de la sesión completa. En el arranque se restaura el último snapshot sin sobrescribir una sesión activa.
2. `core_entities`: persistencia viva limitada a `general_settings` y seis listas núcleo (`customers_registry`, `sales_registry`, `products_registry`, `inventory_registry`, `inventory_movements`, `purchases_registry`).

`src/session_utils.read_list/save_list` solo enviaba esas seis claves a `core_entities`; las demás colecciones seguían viviendo exclusivamente en `st.session_state`. Tampoco existían `read_dict/save_dict` genéricos. El arranque era: snapshot histórico → entidades núcleo → módulos.

`src.session_backup` registra las secciones conocidas en `LIST_SECTIONS`, `DICT_SECTIONS` y `SESSION_KEYS`. Esa lista es la fuente usada por la nueva hidratación; módulos que agreguen secciones al respaldo quedan cubiertos sin mantener otra lista duplicada.

## Decisión de arquitectura

Se añade `session_store(section PRIMARY KEY, data_json, updated_at_utc)` como almacén genérico compatible con SQLite y PostgreSQL. La tabla se crea de forma idempotente desde `src.session_store` utilizando la conexión y el inicializador existentes.

La sesión sigue siendo la caché inmediata:

- `save_list/save_dict`: validan, copian a `st.session_state` y hacen UPSERT de una sola sección.
- `read_list/read_dict`: si la clave falta en la sesión, la recuperan perezosamente de `session_store` y la cachean.
- `general_settings`: se serializa como JSON y se reconstruye como `GeneralSettings` al hidratar.
- arranque: snapshot → `core_entities` → `session_store`. La hidratación nunca reemplaza claves ya presentes y migra una sola vez valores heredados que aún no existan en `session_store`.

`core_entities` y los snapshots se conservan durante la transición para compatibilidad, exportación y recuperación histórica.

## Fallos y modo degradado

Toda operación de `session_store` captura errores de conexión, serialización o esquema, registra la excepción mediante `logging` y deja el detalle en `_session_store_degraded`. La escritura en sesión ocurre antes del intento de BD, por lo que la app continúa operando en modo solo-sesión.

No se reescribe el estado completo en cada rerun: solo se hace UPSERT cuando `save_list`, `save_dict` o la persistencia de configuración reciben un cambio.

## Migración

La migración es no destructiva:

- una sección ya presente en `session_store` se considera autoritativa;
- valores restaurados desde snapshot o cargados desde `core_entities` solo se insertan si la sección no existe;
- ejecutar la hidratación/migración más de una vez no duplica filas por la clave primaria `section`.

## Pruebas añadidas

`tests/test_session_store.py` cubre:

- lista persistida y recuperada tras limpiar `st.session_state`;
- diccionario persistido y recuperado;
- `general_settings` restaurado como `GeneralSettings` con tasas e IVA;
- hidratación que no sobrescribe datos activos;
- BD indisponible con continuidad en modo solo-sesión;
- migración idempotente desde estado heredado/snapshot.

## Riesgos y seguimiento

- Los módulos que escriban directamente en `st.session_state` sin llamar `save_list/save_dict` no activan write-through en ese instante. La cobertura depende de la convención existente; deben migrarse gradualmente a los helpers cuando se detecten excepciones.
- SQLite en hostings efímeros sigue sin ser durable tras reinicios del contenedor. Para producción se requiere `COPYMARY_DATABASE_URL` con PostgreSQL.
- `core_entities` puede retirarse en una fase futura solo después de comprobar que todas las instalaciones migraron correctamente a `session_store`.
