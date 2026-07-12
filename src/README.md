# Código fuente (`src/`)

## Convención de capas

Muchos dominios de negocio están organizados en capas que se extienden entre
sí, cada una agregando funcionalidad sobre la anterior sin reescribirla:

```
dominio.py → dominio_plus.py → dominio_governance.py → dominio_control.py
```

Por ejemplo: `costing.py` → `costing_plus.py` → `costing_governance.py`.
Cada capa hace `from src import dominio_anterior as base` y reutiliza sus
funciones en vez de copiarlas. **Esto no es duplicación de código: es
composición deliberada.** Ver `docs/auditoria-copymary-1.md` para el
contexto de por qué se adoptó este patrón.

Algunas capas finales son solo un alias de una función más completa con otro
nombre (ej. `costing_control.py` simplemente reexporta
`costing_governance.render_costing_governance`), cuando el nombre de menú
deseado no coincide con el nombre de la capa real más completa.

## Cuál versión es "la oficial"

**La fuente de verdad es `src/module_bootstrap.py`.** El menú (`MODULE_RENDERERS`)
registra exactamente una entrada por dominio, siempre apuntando a la capa
más completa. Los archivos base/`_plus` intermedios nunca se registran
directamente — son bloques de construcción internos, no páginas del menú.

Si agregas una capa nueva y más completa a un dominio existente, **actualiza
`module_bootstrap.MODULE_RENDERERS`** para que apunte a la nueva capa. Si te
olvidas, `tests/test_module_registration.py` falla automáticamente: detecta
cuando el menú apunta a una capa que alguien más extendió después.

## Helpers compartidos

`session_utils.py` centraliza los helpers de `st.session_state` que antes
estaban duplicados de forma idéntica en ~80 módulos (`_now`, `_records`/`_rows`,
`_save`, `_item_name`). Al escribir un módulo nuevo, importa desde ahí en vez
de redefinir estos helpers.

## Base de datos

`erp_database.py` es la única fuente de acceso a SQLite (esquema versionado,
migraciones idempotentes). Los módulos de costeo por procesos (`bom_costing.py`,
`bom_multilevel.py`) ya usan esta capa; el resto de los módulos todavía
persiste en `st.session_state` (ver `README.md` en la raíz del repo para el
estado general y lo que falta).
