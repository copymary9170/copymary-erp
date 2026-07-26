# Fase 6B — Matriz de trazabilidad y auditoría final

## Propósito

Este documento consolida la evidencia técnica de la Fase 6B del gestor de metas empresariales y KPI persistentes. Su objetivo es relacionar los criterios del issue maestro con los componentes implementados, los pull requests asociados y la evidencia de prueba disponible.

No sustituye una ejecución real de CI. Mientras no exista un workflow run verificable o una validación local documentada, el estado de las pruebas debe considerarse pendiente.

## Trazabilidad por criterio

| Criterio | Implementación principal | Evidencia histórica | Estado técnico |
|---|---|---|---|
| Persistencia de metas | Repositorio, esquema y servicio de metas | PRs #243, #244, #245 | Implementado |
| Metas por empresa, rol y usuario | Alcance y asignaciones persistentes | PRs #243–#245 | Implementado |
| Herencia por rol sin duplicados | Consulta de metas efectivas | PRs #244–#245 | Implementado |
| Permisos con denegación por defecto | Capa de permisos y administración por rol | PRs #252 y anteriores | Implementado |
| Historial y versionado | `goal_history` y servicio transaccional | PRs #243–#244 | Implementado |
| Rechazo de edición de metas cerradas | Validaciones del servicio | PR #244 | Implementado |
| Validación de fechas y objetivos | Contrato KPI y servicio | PRs #247 y #244 | Implementado |
| Transiciones de estado auditadas | Servicio de metas | PR #244 | Implementado |
| Snapshot final de cierre | Flujo de cierre formal | PR #250 | Implementado |
| Dashboard de Inicio consume metas persistentes | Integración de Inicio | PRs #245–#246 | Implementado |
| Administración de metas | Gestor administrativo y navegación | PRs #248–#249 | Implementado |
| Administración de permisos por rol | Interfaz de permisos | PR #252 | Implementado |
| Migración v15 nativa | `erp_database.initialize_database()` | PR #254 | Implementado |
| Retiro del bootstrap temporal | Eliminación del puente de activación | PR #255 | Implementado |
| Documentación de arquitectura | Documento de Fase 6B | PR #256 | Implementado |
| Pruebas automatizadas | Workflow y pruebas dirigidas | PRs #253–#255 | Añadidas; ejecución no verificada |

## Migración y base de datos

La versión 15 se considera parte de la inicialización fundacional. La migración debe:

1. crear las tablas de metas de forma idempotente;
2. registrar `persistent_business_goals` en `schema_migrations`;
3. funcionar tanto en bases nuevas como en actualizaciones desde v14;
4. no depender de ajustes de versión en memoria;
5. no modificar tablas operativas ajenas a metas.

## Compatibilidad preservada

La Fase 6B no debe alterar el comportamiento de:

- Catálogo;
- Compras;
- Recepción;
- Inventario;
- Producción.

También deben permanecer intactas las reglas especializadas de la industria del papel:

- dimensiones por cuatro lados;
- cortes irregulares;
- cálculo de área;
- gramaje;
- promedios ponderados;
- historial de proveedores;
- costo promedio ponderado.

## Evidencia pendiente

Al momento de crear esta auditoría no existe una ejecución verificable de GitHub Actions asociada al merge más reciente de la Fase 6B. Por tanto:

- no se afirma que la suite pase;
- no se cierra automáticamente el issue #242;
- debe revisarse el primer workflow run disponible;
- cualquier fallo debe resolverse antes del cierre formal.

## Condición de cierre del issue #242

El issue maestro puede cerrarse cuando se cumplan simultáneamente estas condiciones:

1. la migración v15 esté integrada y fusionada;
2. el bootstrap temporal esté retirado;
3. las pruebas de metas, permisos, migración y cierre se ejecuten con resultado satisfactorio;
4. no existan regresiones en módulos operativos;
5. la documentación y esta matriz de trazabilidad estén fusionadas.

## Transición hacia la Fase 7

La Fase 7 podrá utilizar metas persistentes y snapshots para generar alertas preventivas y recomendaciones explicables. Debe mantener el principio de solo lectura sobre los módulos operativos y no realizar correcciones automáticas sin autorización explícita.
