# Blueprint — Gobierno Empresarial

## 1. Identificación

- Nombre del módulo: Gobierno Empresarial
- Código interno: GOV
- Versión del Blueprint: 0.1
- Estado: Borrador inicial
- Responsable funcional: Fundadora / Dirección General
- Responsable técnico: Por definir

## 2. Propósito

Crear el sistema central de dirección, control y toma de decisiones de CopyMary. Este módulo debe evitar que la empresa dependa de la memoria de una sola persona, mantener claridad sobre responsabilidades y conservar evidencia de las decisiones importantes.

## 3. Alcance

### Incluye

- Estructura organizacional.
- Cargos y responsabilidades.
- Objetivos estratégicos.
- Políticas internas.
- Registro de decisiones.
- Comités y reuniones.
- Delegaciones de autoridad.
- Matriz RACI.
- Riesgos empresariales de alto nivel.
- Seguimiento de compromisos.
- Control de versiones de documentos de gobierno.

### No incluye

- Nómina y expedientes laborales.
- Contratos legales detallados.
- Contabilidad operativa.
- Inventario.
- Ejecución de ventas o compras.
- Gestión técnica de usuarios y contraseñas.

## 4. Actores

### Fundadora / Directora General

- Define visión, políticas y objetivos.
- Aprueba decisiones estratégicas.
- Designa responsables.
- Puede cerrar, reemplazar o anular decisiones con justificación.

### Directores o responsables de área

- Proponen decisiones.
- Ejecutan acuerdos aprobados.
- Reportan avances y riesgos.
- No pueden modificar decisiones aprobadas sin autorización.

### Auditor o revisor interno

- Consulta historial.
- Verifica cumplimiento.
- Registra observaciones.
- No modifica decisiones ni políticas.

### Colaborador autorizado

- Consulta documentos aplicables a su trabajo.
- Registra avances en compromisos asignados.
- No accede a información estratégica restringida.

## 5. Casos de uso principales

### GOV-UC-001 Crear una decisión empresarial

- Actor principal: Fundadora o responsable autorizado.
- Objetivo: Registrar una decisión relevante con contexto, responsable, fecha y resultado esperado.
- Precondiciones: Usuario autenticado y autorizado.
- Resultado esperado: Decisión guardada con estado Borrador.

### GOV-UC-002 Aprobar una decisión

- Actor principal: Fundadora / autoridad aprobadora.
- Precondiciones: Decisión en revisión y con información completa.
- Resultado esperado: Decisión pasa a Aprobada y queda bloqueada para edición directa.

### GOV-UC-003 Registrar una política interna

- Actor principal: Fundadora o responsable de área.
- Resultado esperado: Política con versión, vigencia, alcance y aprobador.

### GOV-UC-004 Asignar un compromiso

- Actor principal: Responsable autorizado.
- Resultado esperado: Compromiso con responsable, fecha límite, prioridad y evidencia requerida.

### GOV-UC-005 Registrar una reunión

- Actor principal: Organizador autorizado.
- Resultado esperado: Acta con asistentes, temas, decisiones, compromisos y anexos.

## 6. Procesos y estados

### Estados de una decisión

1. Borrador.
2. En revisión.
3. Aprobada.
4. Rechazada.
5. En ejecución.
6. Cumplida.
7. Cancelada.
8. Archivada.

### Reglas de transición

- Solo una autoridad autorizada puede aprobar o rechazar.
- Una decisión aprobada no se edita directamente; se crea una nueva versión o enmienda.
- Toda cancelación requiere motivo.
- Toda decisión cumplida debe incluir evidencia o nota de cierre.

### Estados de una política

1. Borrador.
2. En revisión.
3. Vigente.
4. Suspendida.
5. Sustituida.
6. Derogada.

## 7. Datos principales

### Entidad: Decisión

- ID único.
- Código legible.
- Título.
- Descripción.
- Contexto.
- Tipo de decisión.
- Área afectada.
- Responsable.
- Aprobador.
- Fecha de creación.
- Fecha de aprobación.
- Estado.
- Prioridad.
- Impacto esperado.
- Riesgos relacionados.
- Evidencias.
- Motivo de cierre o cancelación.
- Versión.

### Entidad: Política

- ID único.
- Código.
- Nombre.
- Objetivo.
- Alcance.
- Contenido.
- Responsable.
- Aprobador.
- Fecha de vigencia.
- Fecha de revisión.
- Estado.
- Versión.
- Documento adjunto.

### Entidad: Compromiso

- ID único.
- Título.
- Descripción.
- Responsable.
- Fecha límite.
- Prioridad.
- Estado.
- Evidencia requerida.
- Evidencia cargada.
- Observaciones.

### Entidad: Reunión

- ID único.
- Tipo.
- Fecha y hora.
- Participantes.
- Agenda.
- Acta.
- Decisiones vinculadas.
- Compromisos vinculados.
- Archivos adjuntos.

## 8. Formularios

### Formulario de decisión

Campos obligatorios:

- Título.
- Descripción.
- Tipo.
- Área afectada.
- Responsable.
- Prioridad.
- Impacto esperado.

Validaciones:

- El título no puede estar vacío.
- El responsable debe ser un usuario activo.
- La fecha límite no puede ser anterior a la fecha de creación.
- No se permite aprobar sin responsable y contexto suficiente.

### Formulario de política

Campos obligatorios:

- Nombre.
- Objetivo.
- Alcance.
- Contenido o documento adjunto.
- Responsable.
- Fecha de vigencia.

## 9. Reglas de negocio

- RN-GOV-001: Ninguna decisión estratégica se considera oficial hasta ser aprobada.
- RN-GOV-002: Toda decisión aprobada debe conservar historial de versiones.
- RN-GOV-003: Toda delegación de autoridad debe tener fecha de inicio, alcance y responsable.
- RN-GOV-004: Ningún usuario puede aprobar una decisión para la que no tenga permiso explícito.
- RN-GOV-005: Toda política vigente debe indicar próxima fecha de revisión.
- RN-GOV-006: Los compromisos vencidos deben marcarse automáticamente como atrasados, sin borrarse.
- RN-GOV-007: Las decisiones canceladas o rechazadas no se eliminan.
- RN-GOV-008: Los documentos de gobierno deben conservar trazabilidad completa.

## 10. Permisos y seguridad

### Consultar

- Según nivel de confidencialidad y área.

### Crear

- Fundadora, directores y responsables autorizados.

### Editar

- Autor mientras esté en Borrador.
- Responsable autorizado durante revisión.

### Aprobar

- Solo roles con autoridad asignada.

### Eliminar

- No se permite eliminar decisiones aprobadas.
- Los borradores pueden anularse con registro de auditoría.

### Información sensible

- Estrategia.
- Finanzas de alto nivel.
- Riesgos críticos.
- Decisiones laborales confidenciales.
- Información legal restringida.

## 11. Auditoría y trazabilidad

Registrar como mínimo:

- Creación.
- Edición.
- Envío a revisión.
- Aprobación.
- Rechazo.
- Cambio de responsable.
- Cambio de fecha límite.
- Carga o eliminación de evidencia.
- Cierre.
- Cancelación.
- Consulta de información altamente confidencial.

## 12. Notificaciones

- Decisión enviada a revisión.
- Decisión aprobada o rechazada.
- Compromiso próximo a vencer.
- Compromiso vencido.
- Política próxima a revisión.
- Riesgo crítico sin responsable.

No deben enviarse notificaciones duplicadas por el mismo evento.

## 13. Reportes e indicadores

- Decisiones por estado.
- Decisiones vencidas o sin cierre.
- Compromisos por responsable.
- Compromisos atrasados.
- Políticas próximas a revisión.
- Riesgos críticos abiertos.
- Porcentaje de acuerdos cumplidos.

## 14. Integraciones

Dependencias futuras:

- Seguridad.
- Usuarios, roles y permisos.
- Auditoría.
- RRHH.
- Legal.
- Reportes.
- Memoria Empresarial.

## 15. Riesgos y controles

### Riesgo: decisiones sin responsable

- Control preventivo: responsable obligatorio.
- Control detectivo: reporte de decisiones huérfanas.

### Riesgo: cambios no autorizados

- Control preventivo: permisos por rol.
- Control detectivo: auditoría de cada modificación.

### Riesgo: documentos obsoletos

- Control preventivo: fecha de revisión obligatoria.
- Control detectivo: alerta de revisión vencida.

### Riesgo: exceso de burocracia

- Control preventivo: formularios proporcionales al nivel de impacto.
- Control detectivo: medir tiempo promedio de aprobación.

## 16. Dependencias

Antes de desarrollar este módulo deben definirse:

- Identidad de usuarios.
- Roles.
- Permisos.
- Auditoría.
- Clasificación de confidencialidad.
- Gestión documental básica.

## 17. Criterios de aceptación

- CA-GOV-001: Un usuario autorizado puede crear una decisión en Borrador.
- CA-GOV-002: Un usuario sin permiso no puede aprobar decisiones.
- CA-GOV-003: Una decisión aprobada conserva su versión original.
- CA-GOV-004: Toda modificación queda registrada en auditoría.
- CA-GOV-005: Un compromiso vencido aparece como atrasado.
- CA-GOV-006: Una política vigente muestra su fecha de próxima revisión.
- CA-GOV-007: Los reportes solo muestran información permitida para el usuario.

## 18. Pruebas mínimas

- Creación de decisión válida.
- Rechazo de formulario incompleto.
- Aprobación por usuario autorizado.
- Bloqueo de aprobación para usuario no autorizado.
- Conservación de historial.
- Cambio de estado válido e inválido.
- Generación de alerta por vencimiento.
- Registro de auditoría.
- Restricción de información confidencial.

## 19. Migración y datos iniciales

Datos iniciales propuestos:

- Visión y filosofía empresarial.
- Estructura organizacional inicial.
- Equipos actuales.
- Lista de responsables.
- Políticas básicas.
- Decisiones estratégicas vigentes.

## 20. Decisiones pendientes

- Definir niveles exactos de confidencialidad.
- Definir matriz de autoridad.
- Definir cargos iniciales.
- Definir si las reuniones tendrán firma digital.
- Definir tiempo de conservación de actas y decisiones.

## 21. Aprobación

- Aprobado por: Pendiente
- Fecha: Pendiente
- Observaciones: Este documento es un borrador funcional inicial y no autoriza todavía el desarrollo del módulo.
