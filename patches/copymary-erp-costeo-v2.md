# CopyMary ERP — Costeo v2

Parche preparado para actualizar:

- `src/bom_costing.py`
- `src/erp_database.py`

Archivo fuente recibido: `copymary-erp-costeo-v2.patch`.

## Alcance

- Costos diferenciados para impresión a color y blanco/negro.
- Prorrateo de materiales por piezas por hoja/anidado.
- Parámetros de sublimación: sustrato, temperatura, tiempo y presión.
- Consumibles recomendados según tipo de material.
- Versionado de recetas para conservar el histórico.
- Migración SQLite idempotente a esquema v2.
- Asociación del trabajo costeado con la tasa de cambio utilizada.

## Validación de compatibilidad

El parche referencia exactamente los blobs actuales de `main`:

- `src/bom_costing.py`: `855c0fc...`
- `src/erp_database.py`: `ec3b870...`

El parche completo permanece como artefacto de origen y debe aplicarse sobre esta rama antes de fusionarla con `main`.
