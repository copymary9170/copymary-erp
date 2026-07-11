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
- **Base de datos SQLite** con esquema versionado y migraciones idempotentes
  (`src/erp_database.py`), incluyendo tabla de auditoría (`audit_events`) con registro
  de antes/después por cada cambio relevante.
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
  - Activos con depreciación
  - Usuarios y roles
- **Pruebas automáticas** con `pytest` (100 tests) cubriendo autenticación, base
  de datos, costeo, inventario, producción, comisiones, caja y conciliación
  financiera (ver `tests/README.md`).

Lo que **todavía no existe**:

- Migración a PostgreSQL (SQLite es el motor real hoy; Postgres está documentado como
  objetivo futuro en `src/erp_database.py`, pero bloqueado hasta agregar el driver).
- Pruebas automáticas para los módulos de negocio (costeo, inventario, producción,
  comisiones, caja) — ver la sección "Qué falta" en `tests/README.md`.
- CI/CD: deliberadamente no se ha configurado GitHub Actions todavía (ver
  `docs/error-real-copymary-1.md` para el porqué).

## Instalar y correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

La primera vez que se abre la app, si no existe ningún usuario, se muestra un
formulario para crear el administrador inicial.

## Correr las pruebas

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Probar desde Streamlit Community Cloud

La aplicación puede probarse completamente desde el navegador, sin Visual Studio Code y sin instalar programas localmente.

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

- `docs/COPYMARY_ENTERPRISE_CONTEXTO_MAESTRO.md`: visión, filosofía y dominios del negocio.
- `docs/ROADMAP_ARQUITECTURA.md`: fases de desarrollo planeadas.
- `docs/auditoria-copymary-1.md` y `docs/error-real-copymary-1.md`: por qué se reinició el proyecto.
- `src/README.md`: convenciones del código fuente.

## Próximo paso recomendado

La lógica de negocio principal (costeo, inventario, producción, comisiones,
caja, conciliación) ya tiene pruebas automáticas. El siguiente paso es
extender la cobertura a los módulos `_plus`/`_control`/`_governance` que
extienden a los de base, y considerar la migración a PostgreSQL documentada
en `src/erp_database.py`.
