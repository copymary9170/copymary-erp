# Fase 6B — Metas empresariales persistentes y KPI

## Estado de la implementación

La Fase 6B convierte las metas configurables de la Fase 6A en registros persistentes, auditables y gobernados por permisos.

La implementación mantiene separados los módulos operativos de Catálogo, Compras, Recepción, Inventario y Producción. Los KPI leen esos módulos sin modificar sus registros.

## Arquitectura

La solución queda distribuida en capas:

1. **Registro KPI**
   - Conserva las definiciones declarativas de los indicadores.
   - Separa definición, formato, dirección y cálculo.

2. **Persistencia**
   - `business_goals`
   - `goal_assignments`
   - `goal_history`
   - `goal_progress_snapshots`

3. **Repositorio y servicios**
   - Centralizan lectura, creación, edición, asignación, transiciones, cierre, historial y snapshots.
   - Evitan acceso SQL directo desde la interfaz.

4. **Permisos**
   - `goal_view`
   - `goal_create`
   - `goal_edit`
   - `goal_assign`
   - `goal_close`
   - `goal_history_view`

   El rol Administrador conserva acceso completo. Los demás roles siguen denegación por defecto hasta recibir permisos explícitos.

5. **Interfaz**
   - El dashboard de Inicio consume metas persistentes aplicables al usuario.
   - El gestor administrativo permite crear, editar, asignar, consultar historial y ejecutar el cierre formal según permisos.

## Migración v15

La migración quedó consolidada dentro de `src/erp_database.py`.

- `SCHEMA_VERSION` es 15.
- `initialize_database()` crea de forma idempotente las tablas e índices de metas.
- La versión se registra como `persistent_business_goals` en `schema_migrations`.
- El bootstrap temporal de v15 fue retirado.

La inicialización fundacional es la única fuente de verdad para el esquema.

## Reglas preservadas

- Una meta cerrada no se edita directamente.
- Las modificaciones relevantes generan historial con actor y fecha.
- El cierre formal crea un snapshot final de progreso.
- Las metas por rol se heredan dinámicamente y no se duplican físicamente por usuario.
- Las consultas efectivas combinan metas de empresa, rol y usuario sin duplicados lógicos.
- Las fechas y valores objetivo se validan antes de persistir.
- Los módulos operativos se consultan en modo de solo lectura para calcular KPI.

## Compatibilidad empresarial

Esta fase no modifica:

- dimensiones de cuatro lados;
- cortes irregulares;
- cálculo de área;
- gramaje;
- promedios ponderados;
- historial de proveedores;
- costo promedio ponderado;
- separación entre Catálogo, Compras, Recepción e Inventario.

## Validación pendiente

Las pruebas automatizadas y el workflow de GitHub Actions existen, pero el cierre técnico debe distinguir entre pruebas añadidas y pruebas realmente ejecutadas. No se debe afirmar que el conjunto pasa mientras no exista una ejecución verificable de CI o una validación local documentada.

## Cierre de la fase

El issue maestro puede cerrarse cuando:

- la migración v15 esté fusionada;
- el bootstrap temporal esté retirado;
- la persistencia, permisos, historial, herencia y cierre formal estén integrados;
- el dashboard consuma metas persistentes;
- la documentación refleje el estado final;
- no existan regresiones conocidas en los módulos operativos.

La siguiente fase puede utilizar las metas persistentes y sus snapshots para generar alertas preventivas y recomendaciones explicables, sin escritura automática sobre los módulos operativos.
