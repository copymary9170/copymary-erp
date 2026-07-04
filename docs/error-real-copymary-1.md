# Error real detectado en `copymary-1`

Fecha: 2026-07-04

## Evidencia aportada

La sección **GitHub Actions** de `copymary-1` muestra decenas de ejecuciones fallidas en la rama `arquitectura-base` con estas señales:

- estado rojo en cada ejecución;
- título `(Unknown event)`;
- workflow identificado como `(Unnamed workflow)`;
- una ejecución nueva por numerosos commits consecutivos.

## Corrección de la auditoría inicial

La revisión inicial del código visible no podía detectar este problema porque el fallo principal no estaba en `app.py`, Legal, Procesos o Dashboard. El problema estaba relacionado con la configuración o ejecución de **GitHub Actions** y el flujo automatizado que generó muchos commits.

## Qué significa

GitHub intentó ejecutar un workflow automatizado, pero el workflow no estaba correctamente identificado o configurado, o falló antes de completar sus trabajos. El patrón también indica que se hicieron demasiados cambios automáticos seguidos sin detenerse a comprobar el resultado de la primera ejecución.

## Riesgos observados

1. Muchos commits automáticos sin validación intermedia.
2. Fallos repetidos del mismo workflow.
3. Ausencia de un nombre claro para el workflow.
4. Posible configuración incorrecta del evento `on` o del archivo YAML.
5. Posible workflow creado en una rama de trabajo sin probarlo primero.
6. El agente siguió modificando el repositorio aunque las ejecuciones anteriores estaban fallando.

## Reglas obligatorias para `copymary-erp`

1. No crear GitHub Actions durante la primera etapa del proyecto.
2. No permitir que un agente haga decenas de commits seguidos sin revisión.
3. Hacer cambios pequeños y comprobar cada commit antes del siguiente.
4. Crear workflows únicamente cuando la aplicación mínima ya funcione.
5. Todo workflow deberá tener un campo `name` claro.
6. Todo workflow deberá declarar eventos `on` válidos y limitados.
7. Probar primero los workflows en una rama específica.
8. Si una ejecución falla, detener nuevos cambios y revisar el log antes de continuar.
9. No usar despliegue, migraciones ni modificaciones de base de datos automáticas sin aprobación.
10. Mantener protegida la rama `main` y trabajar mediante ramas y pull requests cuando el proyecto tenga una base estable.

## Decisión para el repositorio nuevo

`copymary-erp` comenzará sin workflows de GitHub Actions. La primera etapa se limitará a documentación, arquitectura y una aplicación mínima verificable. La automatización se incorporará después, una función a la vez.
