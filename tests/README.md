# Pruebas

Suite de pruebas automáticas con `pytest`. Cada prueba corre con su propia
base de datos SQLite temporal y con `st.session_state` limpio (ver
`conftest.py`), así que las pruebas no interfieren entre sí ni tocan datos reales.

## Cómo correrlas

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Esto corre 235 pruebas contra SQLite. 6 de ellas (`test_erp_database_postgres.py`)
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

## Login sin límite de intentos (corregido)

`auth.authenticate()` no tenía ningún límite: se podía probar contraseñas
contra un mismo correo indefinidamente. Se agregó bloqueo temporal (migración
v5): tras `MAX_FAILED_LOGIN_ATTEMPTS` (5) intentos fallidos consecutivos, la
cuenta se bloquea `LOCKOUT_MINUTES` (15) minutos, incluso si luego se prueba
la contraseña correcta. Un login exitoso resetea el contador. Verificado
extremo a extremo contra SQLite y PostgreSQL reales.

## RRHH y nómina (módulo nuevo)

Revisión de negocio (dueña + finanzas + producción): el sistema no tenía
ninguna forma de registrar empleados ni pagarles — `team_commissions.py`
incluso lo admitía explícitamente ("las comisiones no sustituyen una nómina
legal"). Se agregó `src/payroll.py` (migración v6): empleados, períodos de
nómina, recibos de pago con salario + bonos − deducciones = neto. Alcance
deliberadamente honesto: no calcula prestaciones sociales, utilidades ni
retenciones de ley (varían por país y deben validarse con un contador) — lo
que resuelve es dejar de pagarle a la gente fuera del sistema, con historial
y auditoría de cada pago. Ver `test_payroll.py`.

## Estado de Resultados (módulo nuevo)

`financial_dashboard_plus.py` calculaba una "utilidad estimada" (ventas −
costo estimado), pero no restaba gastos operativos ni nómina — no era un
estado de resultados real. Se agregó `src/income_statement.py`: ingresos
(ventas facturadas del mes, sin canceladas) − costo de ventas = utilidad
bruta; utilidad bruta − gastos operativos − nómina = utilidad neta, con
tendencia de 6 meses y desglose de gastos por categoría. Reutiliza los
mismos datos que ya existen (`sales_registry`, `expense_records`) más la
nómina real (`payroll_entries`) agregada en la ronda anterior — no inventa
fuentes de datos nuevas. Ver `test_income_statement.py`.

## Flujo de caja proyectado (módulo nuevo)

Tercer gap de la revisión de negocio: existían proyecciones sueltas (cartera
por cobrar con vencimientos, presupuesto de gastos) pero ninguna vista
consolidada de "cuánto efectivo voy a tener en 30/60/90 días". Se agregó
`src/cash_flow_forecast.py`: posición de caja actual + cobros esperados
(cuentas por cobrar con vencimiento dentro del horizonte, incluyendo
vencidas) − pagos esperados (cuentas por pagar + gastos recurrentes +
nómina activa según frecuencia de pago). Reutiliza datos existentes
(`cash_movements`, `receivables_registry`, `payables_registry`,
`recurring_expenses`) más la nómina real. Es una proyección declarada como
tal (asume que las cuentas se liquidan en su vencimiento), no una promesa.
Ver `test_cash_flow_forecast.py`.

## Mantenimiento preventivo (módulo nuevo)

Cuarto y último gap de la revisión de negocio: `production_machines` ya
existía (para costeo), pero solo tenía costo de depreciación — no había
calendario de mantenimiento ni alerta de máquina atrasada. Se agregó
`src/machine_maintenance.py` (migración v7): planes de mantenimiento por
máquina (tarea + frecuencia en días), con próxima fecha calculada
automáticamente al registrar cada mantenimiento realizado, y bitácora con
costo acumulado. No reemplaza el manual del fabricante — solo ayuda a no
perder de vista la frecuencia recomendada. Ver `test_machine_maintenance.py`.

## Venta rápida de mostrador (módulo nuevo)

Pensando específicamente en el negocio de CopyMary (imprime, saca copias,
sublima, papelería creativa, encuadernación, toppers, insumos escolares y
de oficina): `commercial.py` exige seleccionar un cliente ya registrado
antes de vender. Eso funciona para pedidos personalizados con seguimiento,
pero es fricción real para el volumen más alto del día a día — alguien que
compra 5 fotocopias no tiene por qué registrarse como cliente.

Se agregó `src/quick_sale.py` (migración v8): tarifario configurable de
servicios de mostrador (fotocopia B/N, color, impresión, escaneo,
plastificado, anillado), con precios editables por el usuario y precargados
la primera vez para no arrancar vacío. Formulario de venta rápida sin
cliente obligatorio: si no se elige uno, se usa/crea un cliente ocasional
único que se reutiliza siempre. Escribe en las mismas tablas que
`commercial.py` (`sales_registry`, `cash_movements`) con los mismos
campos, así que Estado de Resultados, flujo de caja y comisiones lo ven
automáticamente sin cambios — probado con dos tests de integración
explícitos que verifican esta compatibilidad. Ver `test_quick_sale.py`.

## Qué falta (pendiente, no cubierto todavía)

Los módulos `_plus`/`_control`/`_governance` que extienden a los de arriba
(la capa de negocio "extra": historiales, exportaciones, reversos, etc.)
todavía no tienen pruebas propias. La lógica de negocio central de cada
dominio — costeo, inventario, producción/catálogo, comisiones, caja,
conciliación, activos, gastos/presupuesto, RRHH/nómina, estado de
resultados — ya está cubierta, igual que la base de datos (SQLite y
PostgreSQL) y la convención de capas de módulos.

De la revisión de negocio (dueña + finanzas + producción), los 4 gaps
identificados ya están resueltos: RRHH/nómina, Estado de Resultados, flujo
de caja proyectado, y mantenimiento preventivo de máquinas. Lo que sigue
pendiente es extender pruebas a los módulos `_plus`/`_control`/`_governance`
que extienden a los módulos base (mencionado arriba).

## Regla del proyecto

Cada función importante debe probarse antes de integrarse, especialmente
autenticación, permisos, cálculos, inventario, documentos y operaciones que
modifiquen datos.
