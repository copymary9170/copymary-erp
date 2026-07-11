# Pruebas

Suite de pruebas automáticas con `pytest`. Cada prueba corre con su propia
base de datos SQLite temporal y con `st.session_state` limpio (ver
`conftest.py`), así que las pruebas no interfieren entre sí ni tocan datos reales.

## Cómo correrlas

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Esto corre 148 pruebas contra SQLite. 6 de ellas (`test_erp_database_postgres.py`)
además validan el soporte de PostgreSQL, pero se **saltan automáticamente**
si no hay un PostgreSQL accesible. Para incluirlas:

```bash
pip install -r requirements-postgres.txt
export COPYMARY_TEST_POSTGRES_URL="postgresql://usuario:clave@host:5432/copymary_erp_test"
pytest tests/ -v
```

## Cobertura actual

| Archivo | Qué cubre |
|---|---|
| `test_erp_database.py` | Esquema fundacional, migraciones idempotentes, registro de auditoría, tasas de cambio (SQLite) |
| `test_erp_database_postgres.py` | Lo mismo que arriba, pero contra PostgreSQL real, más auth.py y bom_costing.py (que hacen SQL directo) — valida que `_PostgresConnection` traduce bien `?`→`%s`, `INSERT OR IGNORE`→`ON CONFLICT`, y `PRAGMA`→`information_schema` |
| `test_auth.py` | Hash y verificación de contraseñas, permisos por rol (deny-by-default), login/logout, alta de usuarios |
| `test_session_utils.py` | Helpers compartidos de `st.session_state` (antes duplicados en ~80 módulos) |
| `test_money.py` | Formato de moneda y resolución de moneda de sesión |
| `test_costing.py` | Depreciación de activos, costo unitario de inventario, cálculo de precio/ganancia (costeo simple) |
| `test_bom_costing.py` | Costeo por procesos: costo de material según modo de impresión, costo de máquina/consumibles/mano de obra por paso, total de receta multi-paso, margen de reventa |
| `test_inventory.py` | Valuación de stock, alertas de stock mínimo, ajuste de entradas/salidas, costo unitario de movimientos |
| `test_production_orders.py` | Costo/precio de órdenes, filtrado de órdenes abiertas y atrasadas, flujo de estados válidos |
| `test_team_commissions.py` | Cálculo de comisión por porcentaje y por monto fijo, pagos acumulados por colaborador |
| `test_cash_closing_reopen.py` | Cierres activos vs. reabiertos, montos de apertura por método de pago |
| `test_financial_reconciliation.py` | Emparejamiento automático de movimientos con líneas bancarias (tolerancia de monto/fecha, puntaje, referencia) |
| `test_module_registration.py` | Protege la convención de capas `base → plus → control/governance`: falla si el menú no apunta a la capa más completa, o si un módulo registrado no importa |
| `test_lint.py` | Corre `pyflakes` sobre `src/` y falla si hay nombres indefinidos (atrapa bugs tipo `NameError` antes de producción) |
| `test_assets.py` | Depreciación de activos (por unidad, acumulada, tope al 100%), valor restante, actualización de unidades acumuladas |
| `test_expenses_budget.py` | Extracción de mes/año, búsqueda de presupuesto por categoría y mes |
| `test_catalog.py` | Catálogo de producción con receta simple: costo de receta, máximo producible según el material más escaso, validación de disponibilidad, consumo de inventario al producir |

## Soporte de PostgreSQL

`src/erp_database.py` soporta PostgreSQL además de SQLite (activado con
`COPYMARY_DATABASE_URL`). Se probó extremo a extremo contra un PostgreSQL 16
real: creación de esquema, migraciones idempotentes, auditoría, tasas de
cambio, autenticación (`auth.py`) y costeo por procesos (`bom_costing.py`).
El adaptador `_PostgresConnection` traduce automáticamente la sintaxis
específica de SQLite que ya usaba el código (`?` como placeholder,
`INSERT OR IGNORE`, `PRAGMA table_info`) al dialecto de PostgreSQL, así que
ningún otro módulo tuvo que reescribirse.

## Bug real encontrado y corregido

`stock_alerts_plus.py` llamaba a `_item_name(...)` sin definirla ni
importarla — un `NameError` que solo se disparaba al abrir esa pestaña de
Alertas de inventario. Se corrigió centralizando `item_name` en
`session_utils.py` (también deduplicó 3 copias idénticas que existían en
otros módulos) y se agregó `test_lint.py` para que este tipo de error se
detecte automáticamente en el futuro.

## Métricas de dashboard restauradas

`pyflakes` señaló 5 variables calculadas pero nunca usadas
("assigned but never used"). Al revisar cada una, 4 eran tarjetas de métrica
que quedaron calculadas pero jamás mostradas en el panel (probablemente un
diseño de columnas que no se actualizó al agregar el cálculo):

- `clients_crm.py`: "Clientes inactivos" no se mostraba.
- `inventory_plus.py`: los lotes por vencer en 30 días se calculaban pero
  nunca generaban aviso al usuario.
- `order_planning.py`: "Listos para entregar" no se mostraba.
- `suppliers_plus.py`: "Inactivos" no se mostraba.

La quinta (`events` en `catalog_production_plus.py`, `movements` en
`inventory_plus.py`) era una carga de datos realmente muerta, sin ningún uso
pendiente — se eliminó.

## Módulos rotos ya no desaparecen en silencio

`module_bootstrap.py` cargaba cada módulo del menú con un `except Exception:
return None` sin registrar nada — si un módulo tenía un error de sintaxis o
una dependencia rota, simplemente desaparecía del menú sin que nadie se
enterara (la misma familia de riesgo que el bug de `_item_name`, pero a nivel
de módulo completo). Ahora cada fallo de carga:

- se registra con `logging.error(...)` (queda en los logs del servidor), y
- se guarda en `module_bootstrap.FAILED_MODULES`, que `foundation_status.py`
  muestra como una alerta visible en el panel "Fundación técnica" para
  cualquier administrador que lo abra.

## Qué falta (pendiente, no cubierto todavía)

Los módulos `_plus`/`_control`/`_governance` que extienden a los de arriba
(la capa de negocio "extra": historiales, exportaciones, reversos, etc.)
todavía no tienen pruebas propias. La lógica de negocio central de cada
dominio — costeo, inventario, producción/catálogo, comisiones, caja,
conciliación, activos, gastos/presupuesto — ya está cubierta, igual que la
base de datos (SQLite y PostgreSQL) y la convención de capas de módulos.

## Regla del proyecto

Cada función importante debe probarse antes de integrarse, especialmente
autenticación, permisos, cálculos, inventario, documentos y operaciones que
modifiquen datos.
