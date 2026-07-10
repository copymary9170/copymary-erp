# Auditoría arquitectónica inicial — CopyMary Enterprise Core

## 1. Propósito

Este documento registra el estado real del repositorio antes de implementar el Core empresarial. Su objetivo es impedir una migración improvisada, proteger la rama `main` y establecer una ruta controlada hacia la arquitectura objetivo.

## 2. Estado comprobado del repositorio

- La aplicación activa utiliza Python y Streamlit.
- El punto de entrada es `app.py`.
- `requirements.txt` declara únicamente `streamlit>=1.32,<2`.
- No existe `package.json` en la raíz.
- No se comprobó todavía una aplicación Next.js, React, TypeScript, Tailwind, Supabase o PostgreSQL operativa dentro de `main`.
- El punto de entrada actual activa un bootstrap modular y carga `src.app_shell_payments.run_app`.
- La aplicación enlaza numerosos módulos funcionales desde `src/`, incluyendo inventario, compras, proveedores, producción, conciliación financiera, cuentas por pagar, cotizaciones, ventas, comisiones, respaldos y reversos.
- El README de `main` no refleja completamente el volumen actual de módulos y debe considerarse desactualizado.

## 3. Hallazgos críticos

### P0 — Incompatibilidad entre arquitectura declarada y arquitectura implementada

La arquitectura objetivo definida para CopyMary Enterprise es Next.js + React + TypeScript + Tailwind + Supabase + PostgreSQL. Sin embargo, el repositorio ejecutable actual es Streamlit.

No se debe insertar código Next.js dentro de la estructura actual sin decidir primero una estrategia de transición. Hacerlo produciría dos aplicaciones inconexas, duplicación funcional y mayor deuda técnica.

### P0 — No existe todavía una base de seguridad empresarial comprobada

Antes de construir autenticación, multiempresa, roles, permisos, RLS y auditoría se debe confirmar:

- si existe alguna persistencia actual;
- dónde se almacenan datos;
- qué módulos escriben archivos locales;
- qué controles de acceso existen;
- qué operaciones destructivas están habilitadas;
- cómo se administran respaldos y restauraciones.

### P1 — Bootstrap con alto acoplamiento

`src/app_shell_payments.py` importa y registra numerosos módulos en tiempo de carga. Este patrón puede provocar:

- efectos secundarios durante imports;
- dependencia circular;
- fallos globales por un módulo defectuoso;
- dificultad para probar módulos aisladamente;
- crecimiento descontrolado del shell principal.

### P1 — Documentación desactualizada

El README afirma que solo existe una interfaz descriptiva sin operaciones reales, mientras que el código enlaza muchos módulos funcionales. La documentación no puede utilizarse como fuente única para decisiones técnicas.

### P1 — Riesgo de migración masiva

Intentar reescribir simultáneamente todos los módulos en Next.js contradice las reglas del proyecto: cambios pequeños, comprobables y sin decenas de commits automáticos.

## 4. Decisión provisional

Se adopta una transición paralela y controlada:

1. `main` continúa siendo la aplicación Streamlit estable.
2. `arquitectura-base` conserva documentación, decisiones y blueprints.
3. La futura implementación Next.js debe comenzar en una rama dedicada, sin reemplazar `main`.
4. Los módulos de Streamlit actuarán como referencia funcional, no como código para copiar automáticamente.
5. Ningún workflow de GitHub Actions será creado o modificado.

## 5. Estrategia propuesta

### Fase A — Inventario técnico de Streamlit

Documentar:

- todos los archivos en `src/`;
- dependencias entre módulos;
- fuentes de datos;
- archivos persistentes;
- operaciones críticas;
- módulos duplicados;
- funciones con efectos secundarios al importar;
- riesgos de seguridad;
- funcionalidades reutilizables como reglas de negocio.

### Fase B — Contratos funcionales

Por cada módulo existente, separar:

- objetivo;
- entidades;
- reglas de negocio;
- estados;
- validaciones;
- permisos requeridos;
- entradas y salidas;
- reportes;
- auditoría;
- dependencias.

### Fase C — Fundación web empresarial

Crear una aplicación Next.js independiente dentro de una rama de implementación o, después de una decisión formal, dentro de una carpeta claramente aislada. La primera entrega deberá contener únicamente:

- configuración estricta de TypeScript;
- Supabase SSR;
- variables de entorno validadas;
- layout base;
- autenticación;
- perfiles;
- organizaciones;
- empresas;
- membresías;
- roles;
- permisos;
- auditoría inicial;
- RLS probado.

### Fase D — Migración por dominios

Migrar un dominio a la vez, comenzando por el Core y continuando con CRM, ventas, inventario, compras, producción y finanzas.

## 6. Reglas de implementación

- No modificar `main` durante la fase de arquitectura.
- No crear ni modificar `.github/workflows`.
- No copiar módulos completos sin auditoría.
- No implementar permisos solo en la interfaz.
- No crear tablas multiempresa sin RLS.
- No mezclar migraciones de varios dominios.
- No introducir secretos en el repositorio.
- No eliminar módulos Streamlit hasta que su reemplazo tenga paridad funcional comprobada.
- No aprobar una migración sin pruebas de aislamiento entre empresas.

## 7. Primera entrega técnica autorizada

La primera entrega de código web deberá limitarse a:

- estructura base Next.js;
- conexión segura con Supabase;
- esquema inicial de perfiles, organizaciones, empresas y membresías;
- catálogo mínimo de permisos;
- roles;
- asignación de roles;
- funciones de autorización;
- políticas RLS;
- auditoría append-only;
- pruebas de acceso cruzado.

## 8. Criterios de aceptación

La fase inicial se considerará aprobada cuando:

- la aplicación Streamlit continúe intacta;
- la nueva aplicación compile de forma independiente;
- no existan secretos versionados;
- el usuario de una empresa no pueda consultar otra empresa;
- un usuario no pueda asignarse roles;
- las operaciones sensibles creen auditoría;
- las migraciones se ejecuten desde una base limpia;
- exista documentación de reversión;
- no se hayan creado workflows.

## 9. Próxima acción

Realizar el inventario completo de archivos y dependencias del directorio `src/`, identificar el mecanismo real de persistencia y emitir un mapa de migración por dominios antes de escribir el esquema productivo del Core.
