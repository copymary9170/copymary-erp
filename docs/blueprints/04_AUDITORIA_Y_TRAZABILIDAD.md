# Blueprint — Auditoría y Trazabilidad

## 1. Identificación

- Nombre del módulo: Auditoría y Trazabilidad
- Código interno: AUD
- Versión del Blueprint: 0.1
- Estado: Borrador inicial
- Responsable funcional: Dirección General / Auditoría Interna
- Responsable técnico: Por definir

## 2. Propósito

Garantizar que toda acción relevante dentro de CopyMary ERP pueda reconstruirse con precisión: quién hizo qué, cuándo, sobre cuál registro, desde qué sesión, con qué resultado y, cuando aplique, cuál era el valor anterior y cuál quedó después.

## 3. Alcance

### Incluye

- Registro centralizado de eventos.
- Historial de cambios por registro.
- Trazabilidad de aprobaciones.
- Registro de accesos a información sensible.
- Evidencia de exportaciones y descargas.
- Registro de errores críticos.
- Trazabilidad de automatizaciones.
- Conservación y consulta de logs.
- Alertas por eventos anómalos.
- Reportes de auditoría.
- Integridad de los registros de auditoría.

### No incluye

- Monitoreo completo de infraestructura externa.
- Análisis forense avanzado.
- Sustitución de respaldos.
- Gestión completa de incidentes, aunque puede integrarse con Seguridad.

## 4. Principios

- Toda acción crítica debe dejar evidencia.
- Los registros de auditoría no se editan desde la aplicación.
- La auditoría debe ser comprensible por una persona autorizada.
- El nivel de detalle debe ser proporcional al riesgo.
- Los eventos deben conservar contexto suficiente para reconstruir la operación.
- La consulta de auditoría también debe quedar registrada cuando involucre información sensible.
- Los fallos de automatización deben detener procesos posteriores cuando exista riesgo de corrupción o pérdida de datos.

## 5. Actores

### Sistema

- Genera eventos automáticamente.
- Registra resultados exitosos y fallidos.
- Conserva identificadores de correlación.

### Auditor

- Consulta eventos e historiales.
- Filtra y exporta reportes autorizados.
- Registra observaciones.
- No modifica eventos existentes.

### Administrador de seguridad

- Revisa eventos de acceso y privilegios.
- Investiga actividad sospechosa.

### Responsable de módulo

- Consulta trazabilidad de registros bajo su alcance.
- No accede a eventos de otras áreas sin permiso.

### Dirección General

- Consulta eventos críticos y reportes ejecutivos.

## 6. Casos de uso principales

### AUD-UC-001 Registrar evento de negocio

- Actor: Sistema.
- Resultado: Evento guardado con usuario, acción, recurso, resultado y fecha.

### AUD-UC-002 Consultar historial de un registro

- Actor: Usuario autorizado.
- Resultado: Línea de tiempo completa del registro.

### AUD-UC-003 Consultar acciones de un usuario

- Actor: Auditor o Seguridad.
- Resultado: Historial filtrado por período, módulo y tipo de acción.

### AUD-UC-004 Detectar evento anómalo

- Actor: Sistema.
- Resultado: Alerta registrada y enviada al responsable.

### AUD-UC-005 Exportar informe de auditoría

- Actor: Auditor autorizado.
- Resultado: Archivo generado, con alcance, filtros y responsable registrados.

### AUD-UC-006 Registrar fallo de automatización

- Actor: Sistema.
- Resultado: Error registrado con contexto, proceso afectado y decisión de detener o continuar.

## 7. Categorías de eventos

- Autenticación.
- Autorización.
- Usuarios y permisos.
- Creación de registros.
- Edición de registros.
- Aprobaciones y rechazos.
- Anulaciones y eliminaciones lógicas.
- Exportaciones.
- Descargas de archivos.
- Carga y reemplazo de documentos.
- Cambios de configuración.
- Ejecuciones automáticas.
- Errores y excepciones.
- Acceso a información sensible.
- Restauraciones y respaldos.
- Integraciones externas.

## 8. Datos principales

### Entidad: Evento de auditoría

- ID único.
- Fecha y hora exacta.
- Usuario.
- Sesión.
- Módulo.
- Recurso.
- Identificador del registro.
- Acción.
- Resultado: éxito, fallo, denegado, parcial.
- Severidad.
- Dirección IP cuando esté disponible.
- Dispositivo o agente.
- Origen: usuario, sistema, integración, tarea automática.
- Motivo o justificación.
- Identificador de correlación.
- Valor anterior.
- Valor nuevo.
- Metadatos técnicos mínimos.

### Entidad: Alerta de auditoría

- ID.
- Evento origen.
- Tipo de alerta.
- Severidad.
- Fecha de detección.
- Responsable.
- Estado.
- Observaciones.
- Fecha de cierre.

### Entidad: Observación de auditor

- ID.
- Evento o conjunto de eventos relacionado.
- Auditor.
- Fecha.
- Hallazgo.
- Recomendación.
- Responsable de respuesta.
- Estado.

## 9. Reglas de negocio

- RN-AUD-001: Todo evento crítico debe registrarse incluso si la operación falla.
- RN-AUD-002: Los eventos no pueden editarse ni eliminarse desde la interfaz normal.
- RN-AUD-003: Toda exportación de auditoría debe quedar auditada.
- RN-AUD-004: Los valores sensibles deben enmascararse cuando no sea necesario guardar el contenido completo.
- RN-AUD-005: Cada evento debe incluir un identificador de correlación cuando forme parte de un proceso de varios pasos.
- RN-AUD-006: Los cambios de permisos requieren valor anterior y valor nuevo.
- RN-AUD-007: Las consultas de información altamente confidencial deben generar evento.
- RN-AUD-008: Los errores críticos de automatización deben detener el flujo cuando exista riesgo de inconsistencia.
- RN-AUD-009: Ningún usuario puede borrar su propio historial.
- RN-AUD-010: La retención debe definirse por categoría y nivel de riesgo.
- RN-AUD-011: La hora del sistema debe mantenerse consistente y verificable.
- RN-AUD-012: La auditoría no debe almacenar contraseñas, secretos ni tokens en texto plano.

## 10. Niveles de severidad

- Informativo.
- Bajo.
- Medio.
- Alto.
- Crítico.

Eventos críticos iniciales:

- Elevación de privilegios.
- Desactivación masiva de usuarios.
- Exportación masiva de datos sensibles.
- Eliminación lógica de registros financieros.
- Restauración de respaldo.
- Fallo de migración.
- Cambio de configuración de seguridad.
- Acceso repetido denegado a recursos sensibles.

## 11. Historial por registro

Cada registro relevante debe permitir ver:

- fecha y hora;
- usuario;
- acción;
- estado anterior;
- estado nuevo;
- campos modificados;
- motivo;
- aprobación relacionada;
- documentos o evidencias vinculadas.

## 12. Consultas y filtros

- Por usuario.
- Por módulo.
- Por acción.
- Por resultado.
- Por severidad.
- Por rango de fechas.
- Por identificador de registro.
- Por sesión.
- Por dirección IP.
- Por evento correlacionado.

## 13. Permisos

- AUD.EVENT.VIEW
- AUD.EVENT.VIEW_SENSITIVE
- AUD.REPORT.EXPORT
- AUD.ALERT.MANAGE
- AUD.OBSERVATION.CREATE
- AUD.OBSERVATION.CLOSE
- AUD.CONFIG.VIEW
- AUD.CONFIG.MANAGE

La visualización debe respetar el alcance del usuario y el nivel de confidencialidad.

## 14. Alertas

- Múltiples intentos fallidos.
- Acceso fuera de horario habitual.
- Exportación de gran volumen.
- Cambio de rol crítico.
- Acceso a información altamente confidencial.
- Automatización fallida repetidamente.
- Operación masiva inusual.
- Intento de alterar registros de auditoría.

## 15. Reportes e indicadores

- Eventos por módulo.
- Eventos críticos por período.
- Acciones por usuario.
- Accesos denegados.
- Cambios de permisos.
- Exportaciones sensibles.
- Automatizaciones fallidas.
- Tiempo promedio de cierre de alertas.
- Hallazgos abiertos.
- Eventos sin usuario o sin correlación.

## 16. Integridad y conservación

- Los eventos deben almacenarse en una estructura separada de los datos operativos cuando sea técnicamente viable.
- Debe existir respaldo periódico.
- La retención debe ser configurable.
- Los registros deben poder verificarse contra alteraciones.
- La eliminación por vencimiento debe ejecutarse mediante proceso controlado y documentado.

## 17. Riesgos y controles

### Riesgo: auditoría incompleta

- Control preventivo: eventos obligatorios por módulo.
- Control detectivo: reporte de operaciones sin evento asociado.

### Riesgo: exposición de datos sensibles en logs

- Control preventivo: enmascaramiento y exclusión de secretos.
- Control detectivo: revisión periódica de campos registrados.

### Riesgo: modificación de evidencias

- Control preventivo: registros inmutables desde la aplicación.
- Control detectivo: verificación de integridad.

### Riesgo: exceso de volumen

- Control preventivo: clasificación y retención diferenciada.
- Control detectivo: monitoreo de crecimiento.

### Riesgo: automatizaciones que continúan tras fallar

- Control preventivo: regla de parada segura.
- Control detectivo: alerta crítica y bloqueo de pasos posteriores.

## 18. Dependencias

- Seguridad.
- Usuarios, Roles y Permisos.
- Configuración general.
- Respaldos.
- Todos los módulos operativos.

## 19. Criterios de aceptación

- CA-AUD-001: Toda creación, edición, aprobación y anulación crítica genera evento.
- CA-AUD-002: Un usuario normal no puede modificar ni eliminar eventos.
- CA-AUD-003: Los cambios sensibles muestran valor anterior y nuevo.
- CA-AUD-004: Las exportaciones quedan registradas con filtros y responsable.
- CA-AUD-005: Los eventos críticos generan alerta.
- CA-AUD-006: Los secretos no aparecen en logs.
- CA-AUD-007: Un proceso automático fallido no continúa cuando la regla indica parada segura.
- CA-AUD-008: El historial de un registro puede reconstruirse en orden cronológico.
- CA-AUD-009: La consulta de datos altamente confidenciales queda auditada.

## 20. Pruebas mínimas

- Crear registro y verificar evento.
- Editar registro y verificar diferencias.
- Aprobar y rechazar operaciones.
- Intentar modificar evento.
- Exportar informe.
- Generar evento crítico.
- Verificar alerta.
- Simular automatización fallida.
- Confirmar que no se registran secretos.
- Verificar filtros por usuario, fecha y módulo.

## 21. Decisiones pendientes

- Definir tiempos de retención por categoría.
- Definir almacenamiento técnico.
- Definir mecanismo de integridad.
- Definir umbrales de alertas.
- Definir qué campos deben enmascararse.
- Definir volumen máximo de exportación.
- Definir responsables de revisión de alertas.

## 22. Aprobación

- Aprobado por: Pendiente
- Fecha: Pendiente
- Observaciones: Este documento es un borrador funcional inicial y no autoriza todavía el desarrollo del módulo.
