# Pruebas

Suite de pruebas automáticas con `pytest`. Cada prueba corre con su propia
base de datos SQLite temporal y con `st.session_state` limpio (ver
`conftest.py`), así que las pruebas no interfieren entre sí ni tocan datos reales.

## Cómo correrlas

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Cobertura actual

| Archivo | Qué cubre |
|---|---|
| `test_erp_database.py` | Esquema fundacional, migraciones idempotentes, registro de auditoría, tasas de cambio |
| `test_auth.py` | Hash y verificación de contraseñas, permisos por rol (deny-by-default), login/logout, alta de usuarios |
| `test_session_utils.py` | Helpers compartidos de `st.session_state` (antes duplicados en ~80 módulos) |
| `test_money.py` | Formato de moneda y resolución de moneda de sesión |
| `test_costing.py` | Depreciación de activos, costo unitario de inventario, cálculo de precio/ganancia (costeo simple) |
| `test_bom_costing.py` | Costeo por procesos: costo de material según modo de impresión, costo de máquina/consumibles/mano de obra por paso, total de receta multi-paso |
| `test_inventory.py` | Valuación de stock, alertas de stock mínimo, ajuste de entradas/salidas, costo unitario de movimientos |
| `test_production_orders.py` | Costo/precio de órdenes, filtrado de órdenes abiertas y atrasadas, flujo de estados válidos |
| `test_team_commissions.py` | Cálculo de comisión por porcentaje y por monto fijo, pagos acumulados por colaborador |
| `test_cash_closing_reopen.py` | Cierres activos vs. reabiertos, montos de apertura por método de pago |
| `test_financial_reconciliation.py` | Emparejamiento automático de movimientos con líneas bancarias (tolerancia de monto/fecha, puntaje, referencia) |
| `test_lint.py` | Corre `pyflakes` sobre `src/` y falla si hay nombres indefinidos (atrapa bugs tipo `NameError` antes de producción) |

## Bug real encontrado y corregido

`stock_alerts_plus.py` llamaba a `_item_name(...)` sin definirla ni
importarla — un `NameError` que solo se disparaba al abrir esa pestaña de
Alertas de inventario. Se corrigió centralizando `item_name` en
`session_utils.py` (también deduplicó 3 copias idénticas que existían en
otros módulos) y se agregó `test_lint.py` para que este tipo de error se
detecte automáticamente en el futuro.

## Qué falta (pendiente, no cubierto todavía)

Los módulos restantes (`_plus`/`_control`/`_governance` que extienden a los de
arriba, catálogo/producción, activos, gastos y presupuesto) todavía no tienen
pruebas propias. La lógica de negocio principal de cada dominio (costeo,
inventario, producción, comisiones, caja, conciliación) ya está cubierta.

## Regla del proyecto

Cada función importante debe probarse antes de integrarse, especialmente
autenticación, permisos, cálculos, inventario, documentos y operaciones que
modifiquen datos.
