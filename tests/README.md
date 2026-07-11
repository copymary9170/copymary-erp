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

## Qué falta (pendiente, no cubierto todavía)

Producción, comisiones, caja y conciliación financiera todavía no tienen
pruebas propias. Son la siguiente prioridad.

## Regla del proyecto

Cada función importante debe probarse antes de integrarse, especialmente
autenticación, permisos, cálculos, inventario, documentos y operaciones que
modifiquen datos.
