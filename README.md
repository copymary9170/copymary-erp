# CopyMary ERP

Sistema ERP empresarial para CopyMary, creado desde una base limpia y modular.

## Objetivo

Centralizar y organizar las áreas principales del negocio sin repetir los problemas estructurales del repositorio anterior.

## Principios del proyecto

- Arquitectura modular
- Seguridad desde el inicio
- Cambios pequeños y comprobables
- Separación entre interfaz, lógica y datos
- Documentación de decisiones importantes
- No copiar errores ni archivos innecesarios del prototipo anterior

## Estado actual

La rama `main` ya no es un demo estático: es una aplicación Streamlit funcional con
persistencia real en SQLite, autenticación por usuario/contraseña y más de 25 módulos
activos.

Incluye:

- **Autenticación y control de acceso**: login con hash PBKDF2-HMAC-SHA256 (200,000
  iteraciones) y permisos por rol con modelo *deny-by-default* (sin fila explícita de
  permiso = sin acceso). El rol Administrador siempre tiene acceso total.
- **Base de datos**: SQLite por defecto (sin dependencias externas) con esquema
  versionado y migraciones idempotentes, incluyendo tabla de auditoría
  (`audit_events`) con registro de antes/después por cada cambio relevante.
  **PostgreSQL también soportado** para producción multiusuario — se activa
  con `COPYMARY_DATABASE_URL` (ver sección de instalación más abajo).
- **Módulos operativos activos**, entre ellos:
  - Centro de control, panel comercial y panel financiero
  - Clientes y seguimiento comercial, comprobantes
  - Inventario, movimientos de inventario, alertas de stock
  - Costeo (simple y por procesos/BOM multinivel, con margen de reventa
    propio para materiales que se venden tal cual), tasas de cambio
  - Órdenes de producción
  - Ajuste y exportación de precios
  - Caja, conciliación financiera, reapertura de cierres
  - Gastos y presupuesto
  - Comisiones de equipo e historial de comisiones
  - Reversos de pago, anulaciones y ajustes
  - Activos con depreciación, gobierno (mantenimiento, incidencias,
    garantías, reposición) y análisis de costo total de propiedad (TCO):
    costo de compra + mantenimiento unificado de ambas bitácoras, costo
    real por unidad y señal de reponer-vs-reparar
  - Usuarios y roles
  - RRHH y nómina (empleados, períodos, recibos de pago)
  - Estado de Resultados (P&L consolidado, tendencia de 6 meses)
  - Flujo de caja proyectado (posición de efectivo a 30/60/90 días)
  - Mantenimiento preventivo por tiempo y por uso (avisa por lo que ocurra
    primero: p. ej. cuchilla Cameo por metros cortados, cabezal por páginas,
    prensa por planchados), con tareas sugeridas por tipo de equipo, bitácora
    de costo por máquina, contador de horas alimentado automáticamente por
    los trabajos reales confirmados en Costeo por procesos, y descuento real
    de Inventario cuando el repuesto instalado salía de una existencia
  - Venta rápida de mostrador (tarifario configurable, sin cliente obligatorio)
  - Análisis y costeo de impresión: confirma trabajos reales (descuenta papel
    de Inventario y suma uso a la impresora en Activos) y los envía a
    Plastificado, Corte en Cameo o Sublimado, que a su vez descuentan su
    propio material y registran uso de máquina
- **Pruebas automáticas** con `pytest` (241 tests, 6 de ellos específicos de
  PostgreSQL) cubriendo autenticación, base de datos (SQLite y PostgreSQL),
  costeo, inventario, producción, comisiones, caja, conciliación financiera y
  la convención de capas de módulos (ver `tests/README.md`).

Lo que **todavía no existe**:

- Despliegue en un servidor propio o nube real: el proyecto sigue
  documentado para probarse en Streamlit Community Cloud, que no es apto
  para producción con datos reales (ver sección más abajo).
- CI/CD: deliberadamente no se ha configurado GitHub Actions todavía (ver
  `docs/error-real-copymary-1.md` para el porqué).

## Instalar y correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

La primera vez que se abre la app, si no existe ningún usuario, se muestra un
formulario para crear el administrador inicial.

## Usar PostgreSQL en vez de SQLite (recomendado para producción)

SQLite es perfecto para desarrollo/demo, pero no soporta bien varios usuarios
escribiendo datos al mismo tiempo. Para producción con más de una persona
usando el sistema a la vez:

```bash
pip install -r requirements-postgres.txt
export COPYMARY_DATABASE_URL="postgresql://usuario:clave@host:5432/copymary_erp"
streamlit run app.py
```

Con `COPYMARY_DATABASE_URL` definida, toda la app (autenticación, costeo,
inventario, etc.) usa PostgreSQL automáticamente — no hace falta tocar
código. El esquema y las migraciones se crean solos en el primer arranque,
igual que con SQLite.

## Correr las pruebas

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Esto corre contra SQLite (rápido, sin dependencias externas). Para además
validar contra PostgreSQL real:

```bash
pip install -r requirements-postgres.txt
export COPYMARY_TEST_POSTGRES_URL="postgresql://usuario:clave@host:5432/copymary_erp_test"
pytest tests/ -v
```

## Despliegue en producción (self-hosted, sin depender de ningún proveedor)

Para uso real con datos del negocio, la ruta recomendada es un VPS propio con
Docker: app + PostgreSQL + HTTPS automático + respaldos automáticos diarios,
todo administrado con 2-3 comandos. Es independiente de cualquier proveedor
específico — funciona igual en DigitalOcean, Hetzner, AWS, o un servidor
propio.

**Ver [`DEPLOY.md`](./DEPLOY.md) para la guía completa paso a paso.**

## Probar desde Streamlit Community Cloud

La aplicación puede probarse completamente desde el navegador, sin Visual Studio Code y sin instalar programas localmente.

> **Nota:** esto es para probar/demostrar la app, no para producción. Streamlit
> Community Cloud no garantiza uptime, no está pensado para varios usuarios
> concurrentes editando datos reales, y puede reiniciarse sin aviso. Para uso
> real con datos del negocio, usa PostgreSQL (sección de arriba) desplegado en
> un servidor propio o un proveedor cloud con esas garantías.

Configuración de despliegue:

- Repositorio: `copymary9170/copymary-erp`
- Rama: `main`
- Archivo principal: `app.py`

Pasos:

1. Ingresar en Streamlit Community Cloud.
2. Iniciar sesión con GitHub.
3. Seleccionar **Create app**.
4. Elegir el repositorio `copymary9170/copymary-erp`.
5. Seleccionar la rama `main`.
6. Indicar `app.py` como archivo principal.
7. Confirmar el despliegue.

## Documentación adicional

- `DEPLOY.md`: guía completa de despliegue self-hosted (Docker + PostgreSQL + HTTPS + respaldos).
- `docs/COPYMARY_ENTERPRISE_CONTEXTO_MAESTRO.md`: visión, filosofía y dominios del negocio.
- `docs/ROADMAP_ARQUITECTURA.md`: fases de desarrollo planeadas.
- `docs/auditoria-copymary-1.md` y `docs/error-real-copymary-1.md`: por qué se reinició el proyecto.
- `src/README.md`: convenciones del código fuente.

## Próximo paso recomendado

Las bases están completas: pruebas automáticas, autenticación, PostgreSQL, y
ahora una guía de despliegue self-hosted completa (`DEPLOY.md`). El siguiente
paso es genuinamente operativo: contratar el servidor, seguir `DEPLOY.md`, y
empezar a cargar datos reales del negocio.
