# Roadmap de Arquitectura — CopyMary ERP

## Propósito

Construir CopyMary ERP por etapas pequeñas, verificables y documentadas, evitando automatizaciones masivas y módulos incompletos.

## Fase 0 — Gobierno del proyecto

Estado: en curso.

Entregables:

- Contexto maestro del proyecto.
- Reglas de ramas y estabilidad.
- Plantilla oficial de Blueprint.
- Criterios para considerar un módulo listo.
- Registro de decisiones de arquitectura.

## Fase 1 — Fundaciones del ERP

Orden obligatorio:

1. Gobierno Empresarial.
2. Seguridad.
3. Usuarios, roles y permisos.
4. Auditoría y trazabilidad.
5. Configuración general.
6. Respaldos.

Ningún módulo con datos sensibles deberá desarrollarse antes de definir estas bases.

## Fase 2 — Operación comercial mínima

1. CRM.
2. Ventas.
3. Inventario.
4. Compras.
5. Producción.
6. Costeo.
7. Tesorería.

Objetivo: permitir registrar una operación real de principio a fin.

## Fase 3 — Control empresarial

1. Contabilidad.
2. Calidad.
3. Activos.
4. Finanzas Estratégicas.
5. Reportes.

## Fase 4 — Gestión organizacional

1. Mi Jornada.
2. RRHH.
3. Legal.
4. Marketing.
5. Memoria Empresarial.

## Fase 5 — Innovación e inteligencia

1. Laboratorio de Innovación.
2. IA.

La IA no sustituirá controles, permisos, auditoría ni aprobación humana.

## Regla de avance

Un módulo solo pasa de arquitectura a desarrollo cuando tenga:

- Blueprint aprobado.
- Alcance definido.
- Actores y permisos definidos.
- Datos y reglas de negocio definidos.
- Formularios y flujos definidos.
- Criterios de aceptación.
- Riesgos identificados.
- Dependencias documentadas.

## Regla de estabilidad

- `arquitectura-base`: documentación y diseño.
- `main`: únicamente código estable.
- Los cambios se harán de forma pequeña y comprobable.
- Si una validación falla, se detiene el avance hasta entender la causa.
