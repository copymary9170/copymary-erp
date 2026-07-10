# Inventario técnico Fase A — Aplicación Streamlit actual

## 1. Objetivo

Este documento registra la arquitectura realmente implementada en `main`, identifica la persistencia disponible, clasifica los módulos por dominio y define qué partes pueden reutilizarse como conocimiento funcional durante la evolución hacia CopyMary Enterprise.

No autoriza todavía una reescritura masiva ni cambios sobre `main`.

---

## 2. Resumen ejecutivo

La aplicación actual ya no es únicamente una maqueta visual. Es un ERP prototipo amplio construido con Python y Streamlit, desarrollado mediante numerosas capas funcionales añadidas progresivamente.

La arquitectura observable combina dos modelos de datos:

1. Persistencia histórica basada en `st.session_state` y respaldos serializados.
2. Una fundación SQLite reciente para módulos nuevos de producción, costeo, usuarios, roles, permisos y auditoría.

Esto significa que el sistema se encuentra en una transición interna incompleta: una parte de las funciones opera como prototipo en memoria y otra parte utiliza persistencia local.

La aplicación no es todavía apta para operación empresarial multiusuario o SaaS porque carece de aislamiento multiempresa, autenticación productiva, autorización central efectiva, transacciones de dominio y una base PostgreSQL activa.

---

## 3. Punto de entrada y carga modular

### 3.1 Punto de entrada

`app.py` es un punto de entrada mínimo que:

- importa `run_app` desde `src.app_shell_payments`;
- importa `activate_module_bootstrap`;
- activa el registro modular;
- ejecuta la aplicación.

Este cambio fue positivo porque redujo la necesidad de modificar `app.py` con cada módulo nuevo.

### 3.2 Registro central

`src/module_bootstrap.py` centraliza actualmente:

- renderizadores de módulos;
- módulos con efectos secundarios;
- navegación de Productos e inventario;
- navegación administrativa.

El cargador captura cualquier excepción durante los imports y devuelve `None`.

#### Riesgo

El patrón evita que un único módulo derribe toda la aplicación, pero también puede ocultar errores reales. Un módulo puede desaparecer silenciosamente de la navegación sin generar un diagnóstico visible, una alerta o un registro técnico.

#### Recomendación

Sustituir progresivamente la captura genérica por:

- registro estructurado de error;
- nombre del módulo fallido;
- tipo de excepción;
- fecha y hora;
- indicador visible en un panel técnico;
- modo estricto para desarrollo y pruebas.

---

## 4. Persistencia comprobada

## 4.1 SQLite local

`src/erp_database.py` implementa una fundación de datos con SQLite.

Configuración:

- `COPYMARY_DATABASE_URL`;
- `COPYMARY_DB_PATH`;
- valor predeterminado `copymary_erp.sqlite3`.

El módulo bloquea explícitamente PostgreSQL: si la URL comienza por `postgres://` o `postgresql://`, genera una excepción porque todavía no existe driver ni sistema de migraciones compatible.

### Tablas fundacionales actuales

- `schema_migrations`
- `app_users`
- `app_roles`
- `app_permissions`
- `audit_events`
- `exchange_rates`
- `production_materials`
- `production_machines`
- `machine_consumables`
- `product_recipes`
- `recipe_steps`
- `costed_jobs`

Otros módulos crean tablas adicionales mediante `CREATE TABLE IF NOT EXISTS`, por ejemplo el BOM multinivel crea:

- `recipe_components`
- `recipe_versions`

### Evaluación

La fundación SQLite es útil como laboratorio local y permite validar conceptos. No debe considerarse todavía el modelo productivo definitivo.

Limitaciones:

- no existe multiempresa;
- no existen claves foráneas declaradas en la mayoría de relaciones;
- no hay aislamiento por usuario;
- no hay RLS;
- no hay cifrado de campos sensibles;
- no hay migraciones versionadas por archivo;
- el esquema se crea desde funciones de ejecución;
- varios módulos pueden ampliar el esquema de forma independiente;
- la concurrencia está limitada por SQLite y por el modelo de ejecución de Streamlit.

## 4.2 Session State

Una parte importante del ERP histórico continúa almacenando estructuras en `st.session_state`.

Implicaciones:

- los datos pueden depender de la sesión del navegador;
- no existe una fuente única de verdad;
- se dificulta la concurrencia;
- se dificulta la auditoría real;
- la restauración puede sobrescribir conjuntos completos;
- las reglas de integridad dependen de cada pantalla;
- diferentes módulos pueden usar nombres y estructuras incompatibles.

## 4.3 Arquitectura híbrida

La coexistencia de SQLite y `session_state` es actualmente el riesgo técnico más importante de la capa de datos.

No debe migrarse módulo por módulo sin identificar primero:

- qué claves de sesión consume;
- qué claves modifica;
- qué tablas utiliza;
- qué identificadores comparte;
- qué respaldos incluyen sus datos;
- qué otros módulos dependen de ellos.

---

## 5. Dominios funcionales identificados

La clasificación siguiente se basa en los módulos registrados, archivos observados y pull requests fusionados.

### 5.1 Plataforma y control

- Inicio
- Centro de control
- Auditoría de datos
- Fundación técnica
- Configuración general
- Respaldo general
- Restauración y rollback
- Protección contra eliminaciones
- Bootstrap modular

### 5.2 CRM y comercial

- Clientes
- Cotizaciones
- Seguimiento comercial
- Ventas y pedidos
- Comprobantes
- Reportes comerciales
- Panel comercial
- Cuentas por cobrar

### 5.3 Compras y proveedores

- Proveedores
- Inteligencia de proveedores
- Compras
- Control presupuestario de compras
- Recepciones parciales
- Cuentas por pagar
- Calendario y previsión de pagos

### 5.4 Inventario

- Inventario
- Planeación de inventario
- Movimientos de inventario
- Transferencias
- Reservas
- Conteos físicos
- Alertas de inventario
- Reposición
- Ajustes y reversos

### 5.5 Catálogo, precios y costeo

- Catálogo y producción
- Mantenimiento del catálogo
- Costeo
- Gobierno de costeo
- Ajuste de precios
- Gobierno de precios
- Importación y exportación de precios
- Costeo por procesos
- BOM multinivel

### 5.6 Producción

- Órdenes de producción
- Planificación de capacidad
- Agenda de producción y entregas
- Control de calidad
- Lotes
- Variantes
- Reversos de producción
- Retrabajo
- BOM y subensambles

### 5.7 Finanzas y tesorería

- Caja
- Arqueos
- Depósitos bancarios
- Conciliación financiera
- Reapertura de cierre
- Gastos y presupuesto
- Reversos de pagos
- Anulaciones y ajustes
- Panel financiero y cierres
- Activos

### 5.8 Equipo y comisiones

- Equipo
- Metas
- Escalas de comisión
- Anticipos
- Cortes
- Solicitudes de pago
- Historial de comisiones
- Revisiones y conciliaciones

### 5.9 Dominios aún no consolidados en el Core observado

- Autenticación productiva
- Multiempresa
- Sucursales
- Membresías
- RBAC efectivo y centralizado
- Segregación de funciones transversal
- RRHH empresarial completo
- Legal empresarial completo
- Marketing empresarial completo
- Gestión documental transversal
- Integraciones
- IA con gobierno y trazabilidad

---

## 6. Evaluación de la seguridad actual

### P0 — Usuarios y contraseñas no constituyen autenticación productiva

La tabla `app_users` contiene un campo `password_hash`, pero la existencia de una tabla no demuestra un flujo seguro de autenticación, sesiones, MFA, recuperación, bloqueo o revocación.

No se debe ampliar este mecanismo como solución final. La arquitectura objetivo deberá usar un proveedor de identidad probado, inicialmente Supabase Auth, y separar credenciales de perfiles empresariales.

### P0 — Los permisos no están normalizados para escala empresarial

`app_permissions` contiene directamente `role_id`, `module_name`, `action_name` y `allowed`.

Limitaciones:

- mezcla catálogo de permisos con asignación a roles;
- no existe tabla puente independiente;
- no existe alcance por empresa o sucursal;
- no existen denegaciones condicionadas;
- no existe vigencia temporal;
- no existe segregación de funciones;
- no existe política de propiedad del registro.

### P0 — Ausencia de aislamiento multiempresa

Las tablas actuales no incluyen sistemáticamente:

- `organization_id`;
- `company_id`;
- `branch_id`;
- `business_unit_id`;
- `department_id`;
- `cost_center_id`.

Por lo tanto, la base SQLite no debe evolucionar directamente a una oferta SaaS sin rediseñar el modelo de tenancy.

### P1 — Auditoría incompleta

La tabla `audit_events` es una buena base conceptual, pero todavía carece de:

- organización y empresa;
- sucursal;
- sesión;
- IP;
- agente de usuario;
- severidad;
- categoría;
- correlación de solicitud;
- protección append-only en base de datos;
- particionamiento;
- reglas de enmascaramiento.

### P1 — SQL dinámico

Se observaron funciones que construyen nombres de tabla mediante concatenación. Aunque los nombres provienen actualmente del código interno, este patrón debe eliminarse o limitarse mediante listas permitidas antes de exponer entradas externas.

---

## 7. Problemas de arquitectura detectados

### 7.1 Esquema distribuido entre módulos

Cada módulo puede ejecutar `CREATE TABLE IF NOT EXISTS`. Esto acelera el prototipo, pero impide conocer fácilmente el esquema completo y el orden de evolución.

Decisión recomendada:

- congelar la creación oportunista de tablas para nuevas áreas;
- documentar todas las tablas existentes;
- centralizar migraciones futuras;
- versionar cambios de esquema;
- añadir pruebas de actualización desde versiones anteriores.

### 7.2 Reglas de negocio mezcladas con interfaz

Los módulos Streamlit suelen concentrar en el mismo archivo:

- lectura de datos;
- cálculos;
- validación;
- escritura;
- renderizado;
- exportación;
- auditoría.

Esto dificulta pruebas unitarias y migración a otra interfaz.

La migración deberá extraer primero contratos de dominio, no traducir pantallas línea por línea.

### 7.3 Duplicación evolutiva

El historial muestra módulos añadidos en varias capas: `plus`, `control`, `governance`, `intelligence`, loaders y wrappers visibles.

Este patrón ha permitido avanzar sin destruir versiones anteriores, pero produce:

- nombres similares;
- riesgo de activar una versión equivocada;
- dependencias ocultas;
- comportamiento duplicado;
- dificultad para identificar la fuente oficial.

### 7.4 Imports con efectos secundarios

Algunos módulos se importan únicamente para activar modificaciones globales sobre `app_shell`, respaldos o comportamiento de otros módulos.

Este patrón deberá sustituirse por un registro explícito de plugins o servicios.

### 7.5 Excepciones silenciosas

`module_bootstrap` captura `Exception` durante imports y omite el módulo fallido.

Debe añadirse una bitácora técnica antes de seguir aumentando módulos.

---

## 8. Activos reutilizables

Aunque el código actual no deba trasladarse literalmente a Next.js, contiene conocimiento funcional valioso.

### Reutilizable como reglas de negocio

- cálculo de costos por materiales, merma, máquina, electricidad y mano de obra;
- BOM multinivel y detección de ciclos;
- estados de órdenes de producción;
- flujos de aprobación;
- conciliaciones;
- reservas y stock libre;
- alertas de inventario;
- planificación de reposición;
- controles de caja;
- reglas de precios y márgenes;
- reversos mediante movimientos compensatorios;
- revisiones y cierres documentados.

### Reutilizable como catálogo funcional

- campos de formularios;
- indicadores;
- filtros;
- exportaciones;
- estados;
- motivos;
- alertas;
- relaciones entre módulos.

### No reutilizar directamente

- dependencia global de `st.session_state`;
- SQL creado dentro de pantallas;
- autorización visual;
- concatenación libre de SQL;
- imports con efectos secundarios;
- archivos monolíticos de interfaz y lógica;
- almacenamiento de credenciales propio;
- identificadores sin tenancy.

---

## 9. Mapa de migración por prioridad

### Etapa 0 — Estabilización del prototipo

Antes de crear más módulos funcionales:

1. Registrar errores de carga de módulos.
2. Crear un catálogo oficial de módulos y versiones activas.
3. Inventariar tablas SQLite.
4. Inventariar claves `session_state`.
5. Prohibir nuevas tablas fuera de una migración central.
6. Identificar módulos duplicados o superpuestos.
7. Añadir pruebas mínimas de importación.

### Etapa 1 — Core web independiente

Crear en una rama dedicada:

- Next.js;
- TypeScript estricto;
- Tailwind;
- Supabase SSR;
- autenticación;
- organizaciones;
- empresas;
- sucursales;
- membresías;
- roles;
- permisos;
- RLS;
- auditoría append-only.

No copiar todavía módulos de negocio.

### Etapa 2 — Maestros compartidos

- monedas;
- tasas;
- unidades;
- categorías;
- impuestos;
- numeraciones;
- documentos;
- configuraciones;
- centros de costo.

### Etapa 3 — Inventario y catálogo

Se recomienda comenzar por este dominio porque alimenta compras, ventas, producción y costeo.

### Etapa 4 — Compras y proveedores

Migrar después de estabilizar inventario y catálogos.

### Etapa 5 — Ventas y CRM

Migrar clientes, cotizaciones, pedidos, cobros y comprobantes.

### Etapa 6 — Producción y costeo

Migrar recetas, pasos, máquinas, materiales, BOM, órdenes y calidad.

### Etapa 7 — Finanzas

Migrar caja, conciliación, cuentas por pagar, gastos, activos y cierres solo cuando los dominios operativos generen transacciones consistentes.

---

## 10. Decisiones obligatorias antes de escribir el Core productivo

1. Determinar si la nueva aplicación vivirá inicialmente en una carpeta aislada del mismo repositorio o en un repositorio separado.
2. Definir Supabase como plataforma inicial o aprobar otro proveedor PostgreSQL/Auth.
3. Definir el modelo de tenancy.
4. Definir estrategia de migración de datos desde SQLite y respaldos de sesión.
5. Definir qué módulo Streamlit es la versión oficial cuando existen capas múltiples.
6. Definir política de congelamiento funcional del prototipo.
7. Definir criterios de paridad antes de retirar módulos.

---

## 11. Próxima entrega autorizada

La siguiente entrega deberá ser documental y de bajo riesgo:

- catálogo oficial de módulos activos;
- catálogo de tablas SQLite;
- catálogo de claves de `session_state`;
- matriz módulo → datos → dependencias → riesgo → destino de migración;
- ADR sobre convivencia o separación entre Streamlit y Next.js.

No debe iniciarse todavía la migración automática de código ni la modificación de `main`.