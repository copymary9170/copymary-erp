# Blueprint — Seguridad

## 1. Identificación

- Nombre del módulo: Seguridad
- Código interno: SEC
- Versión del Blueprint: 0.1
- Estado: Borrador inicial
- Responsable funcional: Dirección General
- Responsable técnico: Por definir

## 2. Propósito

Proteger la información, las operaciones y la continuidad de CopyMary ERP mediante controles de acceso, clasificación de datos, gestión de sesiones, auditoría, respuesta a incidentes y principios de mínimo privilegio.

## 3. Alcance

### Incluye

- Políticas de acceso.
- Identidad de usuarios.
- Autenticación.
- Autorización.
- Sesiones.
- Roles y permisos.
- Clasificación de información.
- Auditoría de acciones sensibles.
- Gestión de incidentes de seguridad.
- Gestión de secretos y credenciales.
- Reglas para carga y descarga de archivos.
- Bloqueo, recuperación y desactivación de cuentas.
- Revisión periódica de accesos.

### No incluye

- Nómina.
- Gestión completa de expedientes laborales.
- Firma digital legal avanzada.
- Seguridad física del local.
- Administración de infraestructura externa fuera del ERP.

## 4. Principios de seguridad

- Mínimo privilegio.
- Acceso por necesidad laboral.
- Separación de funciones.
- Denegación por defecto.
- Trazabilidad completa.
- Protección proporcional al nivel de sensibilidad.
- No compartir credenciales.
- Ningún secreto debe almacenarse en el código fuente.
- Toda acción crítica debe ser verificable.

## 5. Actores

### Administrador de seguridad

- Configura políticas de seguridad.
- Gestiona roles y permisos.
- Revisa incidentes y auditorías.
- No debe aprobar sus propias elevaciones de privilegios cuando exista otro aprobador disponible.

### Administrador funcional

- Solicita accesos para usuarios de su área.
- Revisa permisos asignados.
- No administra credenciales técnicas.

### Usuario interno

- Accede solo a funciones autorizadas.
- Debe proteger sus credenciales.
- Debe reportar actividad sospechosa.

### Auditor

- Consulta registros y evidencias.
- No modifica configuraciones operativas.

### Sistema

- Aplica bloqueos.
- Registra eventos.
- Expira sesiones.
- Genera alertas.

## 6. Casos de uso principales

### SEC-UC-001 Crear usuario

- Actor principal: Administrador autorizado.
- Resultado esperado: Usuario creado en estado Pendiente de activación.

### SEC-UC-002 Activar cuenta

- Actor principal: Usuario invitado.
- Resultado esperado: Credenciales iniciales sustituidas y cuenta activada.

### SEC-UC-003 Iniciar sesión

- Actor principal: Usuario.
- Resultado esperado: Sesión válida con permisos cargados.

### SEC-UC-004 Bloquear cuenta

- Actor principal: Sistema o administrador autorizado.
- Resultado esperado: Acceso suspendido sin eliminar historial.

### SEC-UC-005 Asignar rol

- Actor principal: Administrador autorizado.
- Resultado esperado: Rol asignado con fecha, motivo y responsable.

### SEC-UC-006 Revisar accesos

- Actor principal: Administrador de seguridad o auditor.
- Resultado esperado: Informe de permisos vigentes, excesivos, vencidos o sin uso.

### SEC-UC-007 Reportar incidente

- Actor principal: Cualquier usuario.
- Resultado esperado: Incidente registrado, clasificado y asignado.

## 7. Estados principales

### Estado de usuario

1. Pendiente de activación.
2. Activo.
3. Bloqueado temporalmente.
4. Suspendido.
5. Desactivado.
6. Eliminación lógica.

### Estado de incidente

1. Reportado.
2. En análisis.
3. Contenido.
4. En investigación.
5. Resuelto.
6. Cerrado.
7. Reabierto.

## 8. Datos principales

### Entidad: Usuario de seguridad

- ID único.
- Nombre completo.
- Identificador de acceso.
- Correo.
- Estado.
- Roles asignados.
- Fecha de creación.
- Fecha de activación.
- Último acceso.
- Intentos fallidos.
- Fecha de bloqueo.
- Motivo de suspensión.
- Responsable de alta.
- Fecha de última revisión de permisos.

### Entidad: Rol

- ID único.
- Nombre.
- Descripción.
- Nivel de sensibilidad.
- Permisos asociados.
- Estado.
- Fecha de creación.
- Responsable.

### Entidad: Permiso

- Código.
- Recurso.
- Acción.
- Alcance.
- Condiciones.
- Nivel de riesgo.

### Entidad: Sesión

- ID.
- Usuario.
- Fecha de inicio.
- Última actividad.
- Fecha de expiración.
- Dispositivo o agente.
- Dirección IP cuando esté disponible.
- Estado.
- Motivo de cierre.

### Entidad: Incidente

- ID.
- Fecha y hora.
- Reportado por.
- Descripción.
- Severidad.
- Categoría.
- Sistemas afectados.
- Datos potencialmente afectados.
- Responsable.
- Acciones de contención.
- Evidencias.
- Estado.
- Causa raíz.
- Lecciones aprendidas.

## 9. Reglas de negocio

- RN-SEC-001: Todo acceso debe estar asociado a una identidad individual.
- RN-SEC-002: Las cuentas compartidas están prohibidas.
- RN-SEC-003: Todo permiso debe derivarse de un rol o excepción aprobada.
- RN-SEC-004: Las excepciones de acceso deben tener fecha de vencimiento.
- RN-SEC-005: Cinco intentos fallidos consecutivos deben bloquear temporalmente la cuenta.
- RN-SEC-006: Las sesiones inactivas deben expirar automáticamente.
- RN-SEC-007: Las cuentas desactivadas no pueden iniciar sesión.
- RN-SEC-008: Los secretos no se guardan en archivos versionados.
- RN-SEC-009: Toda asignación o retiro de permisos debe quedar auditado.
- RN-SEC-010: Las acciones críticas requieren confirmación adicional.
- RN-SEC-011: Los archivos cargados deben validarse por tipo, tamaño y nombre.
- RN-SEC-012: Los permisos deben revisarse periódicamente.
- RN-SEC-013: La eliminación física de evidencias de auditoría está prohibida desde la aplicación.
- RN-SEC-014: Un usuario no puede elevar sus propios privilegios.

## 10. Matriz inicial de acciones sensibles

Requieren auditoría reforzada:

- Crear o desactivar usuarios.
- Asignar o retirar roles.
- Aprobar permisos excepcionales.
- Ver información altamente confidencial.
- Exportar datos masivos.
- Descargar documentos sensibles.
- Modificar configuraciones de seguridad.
- Cerrar incidentes.
- Restaurar respaldos.
- Eliminar lógicamente registros críticos.

## 11. Clasificación de información

### Pública

Información autorizada para difusión externa.

### Interna

Información operativa de uso empresarial.

### Confidencial

Información comercial, financiera, laboral o contractual restringida.

### Altamente confidencial

Credenciales, secretos, datos personales sensibles, estrategia crítica, incidentes y datos financieros restringidos.

Cada registro sensible debe incluir clasificación y reglas de acceso.

## 12. Autenticación

Requisitos iniciales:

- Contraseñas robustas.
- Cambio obligatorio de credencial temporal.
- Almacenamiento mediante hash seguro, nunca texto plano.
- Recuperación de acceso con proceso verificable.
- Invalidación de sesiones al cambiar credenciales o desactivar la cuenta.
- Autenticación multifactor prevista para funciones críticas.

## 13. Autorización

Modelo recomendado:

- Control de acceso basado en roles.
- Permisos por recurso y acción.
- Restricciones adicionales por área, confidencialidad y responsabilidad.
- Denegación por defecto.

Acciones mínimas:

- consultar;
- crear;
- editar;
- aprobar;
- anular;
- exportar;
- administrar;
- ver auditoría.

## 14. Gestión de archivos

- Lista permitida de extensiones.
- Tamaño máximo configurable.
- Renombrado seguro en almacenamiento.
- Bloqueo de archivos ejecutables.
- Registro de quién cargó, descargó o reemplazó un archivo.
- Verificación de contenido cuando la infraestructura lo permita.
- Prohibición de rutas manipulables por el usuario.

## 15. Auditoría y trazabilidad

Cada evento debe registrar:

- usuario;
- fecha y hora;
- acción;
- recurso;
- resultado;
- identificador del registro;
- origen de sesión;
- motivo cuando aplique;
- valor anterior y nuevo para cambios sensibles.

Los registros de auditoría deben ser de solo lectura para usuarios normales.

## 16. Notificaciones

- Inicio de sesión sospechoso.
- Bloqueo de cuenta.
- Cambio de rol.
- Permiso excepcional próximo a vencer.
- Exportación masiva.
- Incidente crítico.
- Revisión de accesos vencida.

## 17. Reportes e indicadores

- Usuarios activos, bloqueados y desactivados.
- Permisos por usuario.
- Roles con privilegios críticos.
- Intentos fallidos.
- Sesiones activas.
- Excepciones de acceso vigentes.
- Incidentes por severidad y estado.
- Tiempo promedio de resolución.
- Accesos sin uso.
- Revisiones de permisos pendientes.

## 18. Riesgos y controles

### Riesgo: privilegios excesivos

- Control preventivo: mínimo privilegio y aprobación.
- Control detectivo: revisión periódica de accesos.

### Riesgo: credenciales expuestas

- Control preventivo: secretos fuera del código y hash seguro.
- Control detectivo: alertas de acceso anómalo.

### Riesgo: eliminación de evidencia

- Control preventivo: auditoría inmutable desde la aplicación.
- Control detectivo: verificación de integridad y respaldos.

### Riesgo: exportación indebida

- Control preventivo: permiso específico y límites.
- Control detectivo: registro y alerta de exportaciones.

### Riesgo: automatización defectuosa

- Control preventivo: no ejecutar workflows ni migraciones automáticas sin revisión.
- Control detectivo: detener cambios cuando una validación falle.

## 19. Dependencias

- Gobierno Empresarial.
- Usuarios.
- Roles y permisos.
- Auditoría.
- Configuración.
- Respaldos.

## 20. Criterios de aceptación

- CA-SEC-001: Una cuenta desactivada no puede iniciar sesión.
- CA-SEC-002: Un usuario sin permiso no puede acceder al recurso restringido.
- CA-SEC-003: Toda asignación de rol queda auditada.
- CA-SEC-004: Las sesiones expiran tras el período configurado.
- CA-SEC-005: Los intentos fallidos producen bloqueo según la regla definida.
- CA-SEC-006: Ningún secreto se encuentra en el repositorio.
- CA-SEC-007: Un usuario no puede elevar sus propios permisos.
- CA-SEC-008: Las exportaciones sensibles quedan registradas.
- CA-SEC-009: Los archivos no permitidos son rechazados.
- CA-SEC-010: Los incidentes críticos generan notificación.

## 21. Pruebas mínimas

- Inicio de sesión válido e inválido.
- Bloqueo por intentos fallidos.
- Expiración de sesión.
- Acceso autorizado y denegado.
- Cambio de rol.
- Intento de autoelevación.
- Desactivación de cuenta.
- Recuperación de acceso.
- Carga de archivo permitido y prohibido.
- Exportación autorizada y no autorizada.
- Registro de auditoría.
- Creación y cierre de incidente.

## 22. Decisiones pendientes

- Definir proveedor o mecanismo de autenticación.
- Definir política exacta de contraseñas.
- Definir duración de sesiones.
- Definir cuándo será obligatorio MFA.
- Definir tiempo de conservación de auditorías.
- Definir límites de exportación.
- Definir extensiones y tamaños permitidos.
- Definir responsables de respuesta a incidentes.

## 23. Aprobación

- Aprobado por: Pendiente
- Fecha: Pendiente
- Observaciones: Este documento es un borrador funcional inicial y no autoriza todavía el desarrollo del módulo.
