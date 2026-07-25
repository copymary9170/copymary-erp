# Auditoría arquitectónica inicial de CopyMary ERP

Fecha: 2026-07-25

## Alcance y método

Esta fase no modifica lógica funcional. Se revisó el arranque real definido por `app.py`, el registro central `app_shell.FUNCTIONAL_MODULES`, la navegación efectiva de `top_navigation_app.py`, las rutas de compras/recepción y la persistencia basada en `st.session_state` y snapshots.

No fue posible ejecutar el repositorio en un entorno local desde esta integración, por lo que la lista de renderers activos se obtiene siguiendo de forma determinista el orden real de activación de `app.py` y cada loader. La próxima fase debe añadir una prueba ejecutable que importe el arranque en modo controlado e inspeccione el registro resultante.

## Renderers activos confirmados por el arranque

El orden relevante es:

1. `activate_inventory_enterprise()` registra Inventario empresarial.
2. `activate_supply_chain_integration()` reemplaza Catálogo, Compras, Recepción e Inventario.
3. `activate_purchases_overview_safe()` envuelve Compras.
4. Los loaders de Inventario sustituyen funciones internas y luego reemplazan/envuelven el renderer de Inventario.
5. `activate_inventory_unified_audit_safe()` añade la auditoría final.
6. `app_shell.FUNCTIONAL_MODULES["Catálogo de artículos"]` se reemplaza al final por la versión reactiva.

Renderers finales relevantes:

| Módulo visible | Renderer final |
|---|---|
| Catálogo de artículos | `src.catalog_items_reactive.render_catalog_items` |
| Compras | wrapper creado por `src.purchases_overview_safe_loader.activate_purchases_overview_safe`; ejecuta primero `src.supply_chain_integration.render_purchases_from_catalog` y después `src.purchases_overview_safe.render_purchases_overview` |
| Recepción de mercancía | `src.supply_chain_integration.render_receiving_from_purchases` |
| Inventario | cadena de wrappers cuyo renderer base operativo es `src.inventory_workspace_safe.render_inventory_workspace_safe`, con guía, diagnósticos, salud, historial y auditoría añadidos por los loaders posteriores |
| Proveedores | `src.purchasing.render_suppliers` salvo un reemplazo posterior fuera de `app.py` no observado en esta fase |
| Movimientos de inventario | `src.inventory_movements.render_inventory_movements` como módulo independiente de navegación; la pestaña interna de Inventario usa `src.inventory_movements_safe.render_inventory_movements_safe` |
| Alertas de inventario | `src.stock_alerts.render_stock_alerts` salvo reemplazo registrado por bootstrap |
| Configuración General | renderer inicial de `src.general_settings`, potencialmente reemplazado por `activate_module_bootstrap()`; requiere captura ejecutable del registro para identificar el callable exacto final |

La navegación efectiva usa `SPECIALTY_AREAS` de `src/top_navigation_app.py` y solo muestra páginas que estén registradas en `app_shell.FUNCTIONAL_MODULES` o en grupos heredados.

## Proliferación y candidatos a código duplicado o inactivo

### Confirmados como no activos en la ruta principal actual

- `src.purchases_plus.render_purchases_plus` no se registra desde `app.py`. La ruta visible de Compras es la integración de catálogo más el resumen seguro.
- `src.goods_receipt.render_goods_receipt` existe como pantalla independiente y la página `pages/91_Recepcion_de_mercancia.py` lo invoca, pero la navegación principal activa registra `src.supply_chain_integration.render_receiving_from_purchases`.
- `src.inventory.render_inventory` permanece en el registro inicial de `app_shell`, pero es reemplazado durante el arranque.
- `src.purchasing.render_purchases` permanece en el registro inicial, pero es reemplazado por la integración y luego envuelto por Compras fase 1.
- El renderer de Inventario definido en `src.supply_chain_integration.render_inventory_stock_only` se registra temporalmente y después es reemplazado por `inventory_workspace_safe`.

### No deben borrarse todavía

- Los módulos `*_safe.py` activos forman una cadena real de monkeypatches y wrappers.
- Los loaders no deben retirarse solo por tener nombres similares; varios son responsables del renderer final.
- Los módulos heredados pueden ser usados por páginas Streamlit directas, pruebas, importaciones internas o restauración de datos.

### Acción recomendada

Crear un manifiesto generado por prueba con:

- nombre visible;
- módulo y nombre calificado del callable final;
- orden de reemplazos;
- archivo que registra cada reemplazo;
- importadores estáticos de cada candidato heredado.

Solo después marcar módulos como `legacy`, emitir advertencias de deprecación y retirarlos en una fase separada.

## Riesgo de doble conteo en recepción

Existen dos modelos de compras:

1. `purchases_registry`, usado por `purchases_plus.py`, con campos `quantity`, `received_quantity` y `receipt_status`.
2. `catalog_purchase_orders`, usado por la separación nueva, con `ordered_quantity`, `received_quantity` y `purchase_status`.

`purchases_plus.py` permite registrar recepciones parciales actualizando únicamente el estado de la compra heredada. En el código revisado no aumenta directamente `inventory_registry`; sin embargo, crea una segunda verdad de recepción que puede divergir de `goods_receipts` y de la orden nueva.

La vía nueva llama `goods_receipt.accept_receipt`, que:

- valida la cantidad;
- comprueba idempotencia por `receipt_id` en `goods_receipts`;
- aumenta `inventory_registry`;
- recalcula costo promedio ponderado;
- registra la recepción aceptada.

Riesgos:

- una compra heredada puede figurar como recibida sin haber generado stock;
- una integración futura puede interpretar `receipt_status` como autorización para aumentar inventario otra vez;
- el mismo hecho comercial puede registrarse en `purchases_registry` y `catalog_purchase_orders` con identificadores distintos;
- la idempotencia actual comprueba `receipt_id`, pero inventario y recibo se guardan en dos escrituras separadas de `session_state`; una interrupción entre ambas puede dejar stock aumentado sin recibo idempotente;
- dos sesiones concurrentes pueden procesar el mismo `receipt_id` porque la comprobación y escritura no son una transacción de base de datos.

Conclusión: `goods_receipt.py` debe ser el único servicio autorizado para aumentar stock por compra, y la recepción heredada debe redirigir a ese servicio o convertirse en una vista de seguimiento sin escritura.

## Riesgos de pérdida de datos por session_state

`session_utils.read_list` y `save_list` leen y escriben únicamente `st.session_state`. Por tanto, cualquier colección que no haya sido incluida en el último snapshot se pierde al terminar la sesión o reiniciar el proceso.

El respaldo principal incluye una lista fija de secciones. En la definición base revisada sí incluye `purchases_registry`, `inventory_registry` e `inventory_movements`, pero no incluye de forma nativa varias colecciones nuevas, entre ellas:

- `catalog_items`;
- `catalog_purchase_orders`;
- `goods_receipts`;
- `inventory_reservations`;
- `inventory_count_sessions`;
- `inventory_metadata_audit`;
- observaciones temporales de salud.

Algunos módulos modifican dinámicamente `session_backup.LIST_SECTIONS` al importarse, pero esto depende del orden de importación y no constituye un esquema persistente central.

La restauración de inicio:

- recupera el snapshot completo solo si la sesión está vacía;
- si detecta cualquier dato en la sesión, restaura únicamente Configuración General;
- captura cualquier excepción y continúa silenciosamente.

Esto crea los siguientes escenarios:

- una clave inicializada con datos parciales puede impedir restaurar el resto del snapshot;
- errores de conexión, JSON o compatibilidad pueden dejar la sesión vacía sin aviso al usuario;
- SQLite en hosting efímero no garantiza supervivencia del snapshot;
- guardar inventario y recibo en claves separadas no ofrece atomicidad;
- las tasas pueden sobrevivir mediante snapshot, pero todavía no son una fuente de verdad transaccional.

## Plan de fases priorizado

### Fase 1 — Observabilidad y pruebas del arranque

- Añadir una prueba que ejecute las activaciones del arranque sin lanzar la UI.
- Generar y verificar el mapa de renderers finales.
- Añadir un registro estructurado de reemplazos de `FUNCTIONAL_MODULES`.
- No retirar módulos.

### Fase 2 — Servicio único de recepción

- Extraer una operación transaccional de recepción.
- Hacer que toda recepción de compra pase por ella.
- Deshabilitar o redirigir la escritura heredada de `purchases_plus.py`.
- Mantener lectura compatible de estados antiguos.
- Añadir pruebas de cantidad aceptada, doble clic, costo promedio y recepción parcial.

### Fase 3 — Persistencia núcleo con compatibilidad

- Crear repositorios para configuración/tasas, catálogo, órdenes de compra, recepciones e inventario.
- Empezar con SQLite y mantener compatibilidad PostgreSQL mediante la conexión central.
- Migrar de forma idempotente desde `session_state` cuando la tabla esté vacía.
- Mantener mirror temporal hacia `session_state` para módulos heredados.
- Incluir las tablas en snapshots o exportaciones compatibles.

### Fase 4 — Consolidación de módulos

- Clasificar cada módulo como activo, adaptador, heredado o muerto.
- Sustituir monkeypatches por un registro explícito de módulos.
- Añadir avisos de deprecación.
- Retirar archivos solo tras confirmar cero importadores, cero páginas y pruebas verdes.

### Fase 5 — Cobertura integral

Pruebas mínimas:

- crear artículo sin datos de compra;
- crear orden enlazada al catálogo sin aumentar stock;
- recibir solo cantidad aceptada;
- doble ejecución del mismo `receipt_id` sin duplicar stock;
- costo promedio ponderado;
- recepción parcial y cierre;
- persistencia tras recrear la sesión;
- compatibilidad de snapshot antiguo.

## Riesgos y decisiones pendientes

- Se debe decidir si `purchases_registry` se migra a `catalog_purchase_orders` o se mantiene como histórico de solo lectura.
- La migración de datos no debe ejecutarse hasta disponer de respaldo verificable y conteos comparativos.
- La idempotencia fuerte requiere restricción única de base de datos sobre `receipt_id` y transacción única para recibo, inventario y estado de orden.
- No debe eliminarse ningún módulo en esta fase.
