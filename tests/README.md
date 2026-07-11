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

## Qué falta (pendiente, no cubierto todavía)

Los módulos de negocio (inventario, costeo, producción, comisiones, caja,
conciliación financiera, etc.) todavía no tienen pruebas propias. Son la
siguiente prioridad, especialmente los cálculos de costeo/precios y los
movimientos de inventario, por su impacto directo en el negocio.

## Regla del proyecto

Cada función importante debe probarse antes de integrarse, especialmente
autenticación, permisos, cálculos, inventario, documentos y operaciones que
modifiquen datos.
