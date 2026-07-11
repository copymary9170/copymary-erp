# Estado real del motor de costeo vs. especificación original

Este documento contrasta la especificación original de "Costeo v2"
(`patches/copymary-erp-costeo-v2.md` y el documento de análisis que la
originó) contra lo que **realmente existe hoy en el código**, para evitar que
se vuelva a trabajar sobre supuestos desactualizados.

## Ya implementado (contrario a lo que sugería el análisis original)

El análisis original se escribió antes de que existieran la base de datos,
la autenticación y el motor de costeo por receta. A la fecha de este
documento, ya están construidos:

- Base de datos SQLite con migraciones (`src/erp_database.py`).
- Autenticación con PBKDF2 + roles y permisos (`src/auth.py`).
- Costo diferenciado color / blanco y negro por material (`unit_cost_color`,
  `unit_cost_bw`).
- Merma % configurable por material (`waste_percent`).
- Costo de máquina por hora (depreciación + mantenimiento) y consumo
  eléctrico por kWh (`production_machines`).
- Cuchillas y otros consumibles de máquina con vida útil propia y tipo de
  material recomendado (`machine_consumables`).
- Parámetros de sublimación por receta: sustrato, temperatura, tiempo,
  presión (`recipe_steps`).
- Tasa de cambio con fecha, y cada trabajo costeado queda ligado a la tasa
  usada ese día (`exchange_rates`, `costed_jobs.exchange_rate_id`).
- Distinción entre material para reventa vs. insumo interno (`use_type`:
  insumo / reventa / mixto).
- Receta/BOM multi-paso: impresión, foil, corte, sublimación,
  encuadernado, armado, empaque, cada paso con su propio material, máquina,
  tiempo y mano de obra (`product_recipes` + `recipe_steps`).
- 107 pruebas automáticas cubriendo esta lógica.

## Corregido en esta revisión

- **Área de diseño vs. área de hoja (nesting).** Los campos
  `design_area_cm2` y `sheet_area_cm2` ya existían en el esquema y se
  capturaban en el formulario, pero no se usaban para nada — el usuario
  tenía que calcular a mano cuántas piezas caben por hoja. Se agregó
  `suggested_pieces_per_sheet()` en `src/bom_costing.py`, que sugiere el
  valor en vivo en el formulario (área hoja ÷ área diseño, redondeado hacia
  abajo). Es una estimación simple por área, no un anidado real con
  rotación de piezas — el usuario puede seguir ajustándolo a mano.

## Aclaración sobre la "duplicación de módulos"

El análisis original marcó como riesgo que módulos como `costing.py` /
`costing_plus.py` / `costing_governance.py` existan en varias versiones. Al
revisar el código, esto **no es duplicación accidental**: es un patrón de
capas deliberado donde cada archivo importa y extiende al anterior
(`costing_governance.py` importa `costing_plus as base`, que a su vez
importa `costing as base`). La duplicación real que sí existía era de
pequeños helpers internos (`_now`, `_save`, `_records`/`_rows`,
`_item_name`) copiados de forma idéntica en ~90 archivos — esa sí se
centralizó en `src/session_utils.py`.

## Lo que sigue pendiente (genuino)

- Migración de SQLite a PostgreSQL para uso multiusuario concurrente
  (documentada como objetivo en `src/erp_database.py`, sin driver agregado
  todavía).
- Detección automática del área de diseño desde el archivo subido (hoy es
  un campo numérico manual, no se analiza el archivo de diseño).
- Pruebas automáticas para los módulos `_plus`/`_control`/`_governance` que
  extienden a los módulos base ya cubiertos.
