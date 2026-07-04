# Blueprint — Configuración General

## 1. Identificación

- Nombre del módulo: Configuración General
- Código interno: CFG
- Versión del Blueprint: 0.1
- Estado: Borrador inicial
- Responsable funcional: Dirección General
- Responsable técnico: Por definir

## 2. Propósito

Centralizar los parámetros empresariales y técnicos que afectan el comportamiento de CopyMary ERP, evitando valores dispersos, cambios sin control y configuraciones distintas entre módulos.

## 3. Alcance

### Incluye

- Datos generales de la empresa.
- Moneda principal y monedas secundarias.
- Zona horaria, formatos de fecha y hora.
- Idioma principal.
- Numeraciones y consecutivos.
- Estados y catálogos compartidos.
- Parámetros de negocio.
- Límites operativos.
- Configuración de notificaciones.
- Configuración documental.
- Parámetros de archivos.
- Configuración de períodos.
- Configuración por ambiente.
- Historial de cambios.

### No incluye

- Usuarios, roles y permisos.
- Credenciales y secretos.
- Configuración técnica exclusiva de integraciones externas.
- Reglas propias de un módulo cuando no sean compartidas.

## 4. Principios

- Toda configuración debe tener propietario.
- Los valores críticos deben documentarse.
- Los cambios deben ser trazables.
- Los parámetros sensibles deben requerir aprobación.
- No se deben codificar valores empresariales directamente en el código cuando deban ser configurables.
- Deben existir valores predeterminados seguros.
- La configuración debe validarse antes de aplicarse.

## 5. Actores

### Administrador de configuración

- Consulta y modifica parámetros autorizados.
- Propone cambios críticos.
- No puede aprobar sus propios cambios sensibles cuando exista separación de funciones.

### Aprobador de configuración

- Revisa impacto.
- Aprueba o rechaza cambios críticos.

### Responsable de módulo

- Consulta parámetros bajo su alcance.
- Solicita cambios.

### Auditor

- Consulta historial y justificaciones.
- No modifica configuraciones.

### Sistema

- Aplica validaciones.
- Activa cambios según fecha efectiva.
- Registra fallos de aplicación.

## 6. Casos de uso principales

### CFG-UC-001 Consultar configuración

- Actor: Usuario autorizado.
- Resultado: Visualización de parámetros según alcance y confidencialidad.

### CFG-UC-002 Modificar parámetro no crítico

- Actor: Administrador autorizado.
- Resultado: Cambio aplicado y auditado.

### CFG-UC-003 Solicitar cambio crítico

- Actor: Administrador o responsable de módulo.
- Resultado: Solicitud pendiente de aprobación.

### CFG-UC-004 Aprobar cambio crítico

- Actor: Aprobador autorizado.
- Resultado: Cambio programado o aplicado.

### CFG-UC-005 Programar vigencia

- Actor: Administrador autorizado.
- Resultado: Configuración futura con fecha de inicio y, cuando aplique, fecha de fin.

### CFG-UC-006 Restaurar valor anterior

- Actor: Administrador autorizado.
- Resultado: Nueva versión basada en una configuración previa, sin borrar historial.

## 7. Categorías iniciales

### Empresa

- Nombre comercial.
- Razón social cuando exista.
- Identificación fiscal.
- Dirección.
- Datos de contacto.
- Logo.
- Zona horaria.

### Finanzas

- Moneda principal.
- Decimales.
- Método de redondeo.
- Tasa de cambio de referencia.
- Política de actualización de tasas.

### Documentos

- Prefijos.
- Consecutivos.
- Plantillas.
- Tamaño máximo de archivos.
- Extensiones permitidas.
- Clasificación predeterminada.

### Operación

- Horario empresarial.
- Días laborables.
- Tolerancias.
- Prioridades.
- Estados compartidos.

### Notificaciones

- Canales habilitados.
- Horarios silenciosos.
- Frecuencia.
- Reglas para evitar duplicados.

### Seguridad

- Duración de sesión.
- Intentos fallidos.
- Periodicidad de revisión de accesos.
- Requisitos de confirmación adicional.

Los secretos no se almacenan en este módulo.

## 8. Datos principales

### Entidad: Parámetro

- ID único.
- Código.
- Nombre.
- Descripción.
- Categoría.
- Tipo de dato.
- Valor actual.
- Valor predeterminado.
- Unidad.
- Módulo propietario.
- Nivel de criticidad.
- Nivel de confidencialidad.
- Requiere aprobación.
- Permite vigencia futura.
- Estado.

### Entidad: Versión de configuración

- Parámetro.
- Valor anterior.
- Valor nuevo.
- Fecha de solicitud.
- Fecha de aprobación.
- Fecha efectiva.
- Fecha de fin.
- Solicitante.
- Aprobador.
- Motivo.
- Estado.

### Entidad: Catálogo compartido

- Código.
- Nombre.
- Descripción.
- Valores permitidos.
- Orden.
- Estado.
- Vigencia.
- Módulos consumidores.

## 9. Tipos de datos permitidos

- Texto.
- Número entero.
- Número decimal.
- Booleano.
- Fecha.
- Fecha y hora.
- Lista.
- Catálogo.
- Porcentaje.
- Moneda.
- Duración.
- Referencia a entidad.

Cada tipo debe tener validaciones propias.

## 10. Estados

### Estado de parámetro

1. Activo.
2. Inactivo.
3. Obsoleto.
4. Bloqueado.

### Estado de cambio

1. Borrador.
2. Pendiente de aprobación.
3. Aprobado.
4. Rechazado.
5. Programado.
6. Aplicado.
7. Fallido.
8. Revertido.

## 11. Reglas de negocio

- RN-CFG-001: Todo parámetro debe tener código único.
- RN-CFG-002: Todo parámetro debe indicar propietario y criticidad.
- RN-CFG-003: Los cambios críticos requieren aprobación.
- RN-CFG-004: Un aprobador no puede aprobar su propio cambio crítico.
- RN-CFG-005: Ningún cambio elimina el historial anterior.
- RN-CFG-006: Los valores deben validarse antes de aplicarse.
- RN-CFG-007: Los secretos y credenciales no se almacenan como configuración visible.
- RN-CFG-008: Los parámetros obsoletos no pueden usarse en nuevos procesos.
- RN-CFG-009: Los cambios programados deben aplicarse una sola vez.
- RN-CFG-010: Si un cambio falla, el valor anterior debe permanecer activo.
- RN-CFG-011: Los consecutivos no pueden retroceder ni duplicarse.
- RN-CFG-012: Las configuraciones de ambiente no deben mezclarse entre desarrollo, prueba y producción.
- RN-CFG-013: Todo parámetro utilizado por varios módulos debe documentar sus consumidores.

## 12. Formularios

### Formulario de parámetro

- Código.
- Nombre.
- Descripción.
- Categoría.
- Tipo.
- Valor predeterminado.
- Validaciones.
- Propietario.
- Criticidad.
- Confidencialidad.
- Requiere aprobación.

### Formulario de cambio

- Parámetro.
- Valor actual.
- Valor propuesto.
- Motivo.
- Fecha efectiva.
- Fecha de fin si aplica.
- Impacto esperado.
- Plan de reversión para cambios críticos.

### Formulario de catálogo

- Código.
- Nombre.
- Valores.
- Orden.
- Estado.
- Vigencia.

## 13. Permisos

- CFG.PARAMETER.VIEW
- CFG.PARAMETER.VIEW_SENSITIVE
- CFG.PARAMETER.CREATE
- CFG.PARAMETER.EDIT
- CFG.CHANGE.REQUEST
- CFG.CHANGE.APPROVE
- CFG.CHANGE.REJECT
- CFG.CHANGE.REVERT
- CFG.CATALOG.MANAGE
- CFG.HISTORY.VIEW

## 14. Auditoría

Registrar:

- creación de parámetros;
- modificación;
- solicitud de cambio;
- aprobación o rechazo;
- aplicación;
- fallo;
- reversión;
- activación o desactivación;
- consulta de valores sensibles;
- cambios de consecutivos;
- importación o exportación de configuración.

## 15. Notificaciones

- Cambio crítico pendiente.
- Cambio aprobado o rechazado.
- Cambio programado próximo a entrar en vigencia.
- Fallo de aplicación.
- Parámetro obsoleto todavía en uso.
- Consecutivo próximo a límite técnico.

## 16. Reportes e indicadores

- Cambios por período.
- Cambios críticos pendientes.
- Fallos de aplicación.
- Parámetros sin propietario.
- Parámetros obsoletos en uso.
- Configuraciones por módulo.
- Cambios revertidos.
- Tiempo promedio de aprobación.

## 17. Integraciones

- Seguridad.
- Auditoría.
- Todos los módulos consumidores.
- Respaldos.
- Gestión documental.

## 18. Riesgos y controles

### Riesgo: cambio incorrecto afecta varios módulos

- Control preventivo: validación, aprobación e impacto documentado.
- Control detectivo: monitoreo posterior y plan de reversión.

### Riesgo: valores inconsistentes entre ambientes

- Control preventivo: separación por ambiente.
- Control detectivo: comparación de configuraciones.

### Riesgo: secretos visibles

- Control preventivo: almacenamiento separado de secretos.
- Control detectivo: revisión automática y manual.

### Riesgo: duplicación de consecutivos

- Control preventivo: control transaccional.
- Control detectivo: validación de unicidad.

### Riesgo: cambio fallido deja sistema inconsistente

- Control preventivo: aplicación atómica cuando sea posible.
- Control detectivo: rollback y alerta.

## 19. Dependencias

- Gobierno Empresarial.
- Seguridad.
- Usuarios, Roles y Permisos.
- Auditoría y Trazabilidad.

## 20. Criterios de aceptación

- CA-CFG-001: Un parámetro crítico no puede cambiarse sin aprobación.
- CA-CFG-002: Un usuario no puede aprobar su propio cambio crítico.
- CA-CFG-003: Un valor inválido es rechazado antes de aplicarse.
- CA-CFG-004: Un cambio fallido conserva el valor anterior.
- CA-CFG-005: Todo cambio queda auditado.
- CA-CFG-006: Los secretos no aparecen en la interfaz ni en el repositorio.
- CA-CFG-007: Los cambios programados se aplican en la fecha definida.
- CA-CFG-008: Los consecutivos no se duplican.
- CA-CFG-009: El historial permite reconstruir todos los valores anteriores.

## 21. Pruebas mínimas

- Crear parámetro válido.
- Rechazar código duplicado.
- Cambiar parámetro no crítico.
- Solicitar y aprobar cambio crítico.
- Intentar autoaprobación.
- Programar vigencia futura.
- Simular fallo de aplicación.
- Verificar reversión.
- Validar consecutivos.
- Verificar restricciones por ambiente.
- Confirmar auditoría completa.

## 22. Decisiones pendientes

- Definir catálogo inicial de parámetros.
- Definir ambientes oficiales.
- Definir responsables por categoría.
- Definir política de tasas de cambio.
- Definir formatos documentales.
- Definir límites de archivos.
- Definir mecanismo técnico para secretos.
- Definir cuáles cambios requieren doble aprobación.

## 23. Aprobación

- Aprobado por: Pendiente
- Fecha: Pendiente
- Observaciones: Este documento es un borrador funcional inicial y no autoriza todavía el desarrollo del módulo.
