# Blueprint — Usuarios, Roles y Permisos

## 1. Identificación

- Nombre del módulo: Usuarios, Roles y Permisos
- Código interno: IAM
- Versión del Blueprint: 0.1
- Estado: Borrador inicial
- Responsable funcional: Dirección General
- Responsable técnico: Por definir

## 2. Propósito

Administrar quién puede entrar a CopyMary ERP, qué puede ver, qué puede hacer y bajo qué condiciones. Este módulo debe aplicar mínimo privilegio, separación de funciones, trazabilidad y control por área, cargo y nivel de confidencialidad.

## 3. Alcance

### Incluye

- Alta, activación, suspensión y desactivación de usuarios.
- Catálogo de roles.
- Catálogo de permisos.
- Asignación de roles a usuarios.
- Permisos temporales y excepcionales.
- Restricciones por área, sede, proceso o confidencialidad.
- Revisión periódica de accesos.
- Matriz de segregación de funciones.
- Historial de cambios de acceso.
- Sustituciones temporales por vacaciones, reposo o ausencia.

### No incluye

- Nómina.
- Expedientes laborales completos.
- Inicio de sesión técnico y almacenamiento de contraseñas, que pertenecen al Blueprint de Seguridad.
- Firma electrónica avanzada.

## 4. Principios

- Todo acceso pertenece a una persona identificable.
- Ningún usuario recibe más permisos de los necesarios.
- Los permisos se asignan preferiblemente mediante roles.
- Las excepciones deben ser justificadas, aprobadas y temporales.
- Un usuario no puede aprobar su propia elevación de privilegios.
- Los accesos se retiran cuando dejan de ser necesarios.
- La denegación es el comportamiento predeterminado.

## 5. Actores

### Administrador de accesos

- Crea y mantiene usuarios.
- Asigna roles aprobados.
- Ejecuta suspensiones y bajas.
- No aprueba sus propias excepciones.

### Aprobador de accesos

- Revisa solicitudes.
- Aprueba o rechaza roles sensibles.
- Verifica necesidad laboral y segregación de funciones.

### Responsable de área

- Solicita accesos para integrantes de su área.
- Revisa periódicamente los permisos asignados.
- Informa cambios de cargo o salida.

### Auditor

- Consulta asignaciones, revisiones y excepciones.
- No modifica permisos.

### Usuario

- Consulta sus accesos vigentes.
- Solicita correcciones o accesos adicionales.
- No puede modificar sus propios privilegios.

## 6. Casos de uso principales

### IAM-UC-001 Crear usuario

- Actor: Administrador de accesos.
- Precondición: Existe autorización de alta.
- Resultado: Usuario creado en estado Pendiente de activación.

### IAM-UC-002 Asignar rol

- Actor: Administrador de accesos.
- Precondición: Rol aprobado y compatible con las funciones del usuario.
- Resultado: Asignación registrada con fecha, responsable y motivo.

### IAM-UC-003 Solicitar acceso excepcional

- Actor: Usuario o responsable de área.
- Resultado: Solicitud en estado Pendiente, con vigencia y justificación.

### IAM-UC-004 Aprobar acceso sensible

- Actor: Aprobador autorizado.
- Resultado: Acceso concedido o rechazado con trazabilidad.

### IAM-UC-005 Suspender usuario

- Actor: Administrador autorizado.
- Resultado: Usuario sin acceso, conservando historial.

### IAM-UC-006 Revisar accesos periódicamente

- Actor: Responsable de área o auditor.
- Resultado: Confirmación, reducción o retiro de accesos.

### IAM-UC-007 Delegar funciones temporalmente

- Actor: Responsable autorizado.
- Resultado: Permisos temporales con inicio, fin y alcance definidos.

## 7. Estados

### Estado de usuario

1. Pendiente de activación.
2. Activo.
3. Bloqueado temporalmente.
4. Suspendido.
5. Desactivado.
6. Archivado.

### Estado de una asignación

1. Pendiente.
2. Activa.
3. Rechazada.
4. Vencida.
5. Revocada.
6. Suspendida.

### Estado de una revisión de acceso

1. Pendiente.
2. En revisión.
3. Confirmada.
4. Requiere ajuste.
5. Cerrada.

## 8. Datos principales

### Entidad: Usuario

- ID único.
- Nombre completo.
- Identificador de acceso.
- Correo.
- Área.
- Cargo.
- Responsable directo.
- Estado.
- Fecha de alta.
- Fecha de activación.
- Fecha de baja.
- Motivo de suspensión o desactivación.
- Nivel máximo de confidencialidad permitido.

### Entidad: Rol

- ID.
- Código.
- Nombre.
- Descripción.
- Área propietaria.
- Nivel de riesgo.
- Estado.
- Permisos incluidos.
- Roles incompatibles.
- Requiere aprobación especial.

### Entidad: Permiso

- Código.
- Módulo.
- Recurso.
- Acción.
- Alcance.
- Nivel de riesgo.
- Requiere auditoría reforzada.

### Entidad: Asignación de acceso

- Usuario.
- Rol o permiso.
- Tipo: permanente, temporal o excepcional.
- Fecha de inicio.
- Fecha de fin.
- Justificación.
- Solicitante.
- Aprobador.
- Estado.
- Fecha de última revisión.

### Entidad: Revisión de acceso

- Período.
- Área.
- Responsable revisor.
- Usuarios incluidos.
- Resultado por usuario.
- Ajustes requeridos.
- Fecha de cierre.

## 9. Acciones normalizadas

Cada módulo deberá usar, cuando corresponda, estas acciones estándar:

- consultar;
- crear;
- editar;
- aprobar;
- rechazar;
- anular;
- eliminar lógicamente;
- exportar;
- administrar;
- ver auditoría;
- cargar archivos;
- descargar archivos;
- ejecutar procesos sensibles.

## 10. Reglas de negocio

- RN-IAM-001: Todo usuario debe tener un responsable y un área definidos antes de activarse.
- RN-IAM-002: Los permisos deben asignarse mediante roles, salvo excepción aprobada.
- RN-IAM-003: Toda excepción debe incluir motivo, aprobador y fecha de vencimiento.
- RN-IAM-004: Un usuario no puede aprobar una solicitud que lo beneficie directamente.
- RN-IAM-005: Los roles incompatibles no pueden coexistir en el mismo usuario sin control compensatorio aprobado.
- RN-IAM-006: Los accesos temporales deben vencer automáticamente.
- RN-IAM-007: La desactivación de un usuario revoca todas sus sesiones y asignaciones activas.
- RN-IAM-008: Ninguna asignación revocada o vencida se elimina del historial.
- RN-IAM-009: Todo cambio de cargo debe generar revisión de accesos.
- RN-IAM-010: Toda salida de personal debe generar desactivación inmediata o en la fecha autorizada.
- RN-IAM-011: Los accesos críticos requieren aprobación reforzada.
- RN-IAM-012: Los usuarios sin actividad durante el período definido deben entrar en revisión.

## 11. Matriz inicial de segregación de funciones

No deben concentrarse sin control adicional las siguientes combinaciones:

- Crear proveedor y aprobar pagos.
- Crear producto y modificar costos finales sin revisión.
- Registrar venta y aprobar devolución propia.
- Crear usuario y aprobar privilegios críticos para ese mismo usuario.
- Registrar asiento y aprobar el mismo asiento.
- Crear orden de compra y aprobar su pago.
- Administrar respaldos y eliminar auditorías.

Las excepciones deben documentar el control compensatorio.

## 12. Formularios

### Formulario de usuario

Campos obligatorios:

- Nombre completo.
- Correo o identificador.
- Área.
- Cargo.
- Responsable.
- Fecha de inicio.

Validaciones:

- Identificador único.
- Responsable activo.
- Área y cargo vigentes.
- No activar sin rol mínimo aprobado.

### Formulario de solicitud de acceso

- Usuario beneficiario.
- Rol o permiso solicitado.
- Justificación.
- Fecha de inicio.
- Fecha de fin si es temporal.
- Responsable solicitante.
- Nivel de urgencia.

### Formulario de revisión

- Usuario.
- Accesos vigentes.
- Confirmar, reducir o revocar.
- Justificación.
- Observaciones.

## 13. Permisos del propio módulo

- IAM.USER.VIEW
- IAM.USER.CREATE
- IAM.USER.EDIT
- IAM.USER.SUSPEND
- IAM.USER.DEACTIVATE
- IAM.ROLE.VIEW
- IAM.ROLE.CREATE
- IAM.ROLE.EDIT
- IAM.ROLE.ASSIGN
- IAM.ACCESS.REQUEST
- IAM.ACCESS.APPROVE
- IAM.ACCESS.REVOKE
- IAM.REVIEW.EXECUTE
- IAM.AUDIT.VIEW

## 14. Auditoría

Registrar como mínimo:

- creación de usuario;
- activación;
- suspensión;
- desactivación;
- cambio de área o cargo;
- creación o edición de rol;
- asignación y retiro de permisos;
- aprobación y rechazo de solicitudes;
- vencimiento automático;
- revisión de accesos;
- intento de autoelevación;
- intento de combinar roles incompatibles.

## 15. Notificaciones

- Usuario pendiente de activación.
- Solicitud de acceso pendiente.
- Acceso aprobado o rechazado.
- Permiso temporal próximo a vencer.
- Revisión periódica pendiente.
- Usuario suspendido o desactivado.
- Conflicto de segregación detectado.

## 16. Reportes e indicadores

- Usuarios por estado.
- Usuarios por área y cargo.
- Roles por nivel de riesgo.
- Permisos críticos por usuario.
- Excepciones vigentes.
- Accesos próximos a vencer.
- Revisiones pendientes.
- Usuarios sin actividad.
- Conflictos de segregación.
- Tiempo promedio de aprobación.

## 17. Riesgos y controles

### Riesgo: acumulación de privilegios

- Control preventivo: roles estándar y segregación.
- Control detectivo: revisión periódica.

### Riesgo: acceso tras salida del personal

- Control preventivo: flujo obligatorio de baja.
- Control detectivo: reporte de usuarios activos sin vínculo vigente.

### Riesgo: permisos temporales permanentes por error

- Control preventivo: fecha de vencimiento obligatoria.
- Control detectivo: alerta y revocación automática.

### Riesgo: autoaprobación

- Control preventivo: separación entre solicitante y aprobador.
- Control detectivo: auditoría y rechazo automático.

## 18. Dependencias

- Seguridad.
- Gobierno Empresarial.
- Configuración general.
- Auditoría.
- RRHH para sincronizar altas, cambios y bajas cuando ese módulo exista.

## 19. Criterios de aceptación

- CA-IAM-001: Un usuario no puede activarse sin área, cargo y responsable.
- CA-IAM-002: Un usuario no puede aprobar su propia elevación de privilegios.
- CA-IAM-003: Un permiso temporal vence automáticamente.
- CA-IAM-004: Una cuenta desactivada pierde todos sus accesos activos.
- CA-IAM-005: Los roles incompatibles generan bloqueo o alerta según configuración.
- CA-IAM-006: Toda asignación y revocación queda auditada.
- CA-IAM-007: Un responsable puede revisar únicamente los usuarios bajo su alcance.
- CA-IAM-008: El historial permanece disponible después de la revocación.

## 20. Pruebas mínimas

- Crear usuario válido e inválido.
- Activar usuario con y sin rol mínimo.
- Asignar rol permitido.
- Rechazar rol incompatible.
- Solicitar acceso temporal.
- Vencer acceso automáticamente.
- Intentar autoaprobación.
- Suspender y desactivar cuenta.
- Revisar accesos por área.
- Verificar auditoría completa.

## 21. Decisiones pendientes

- Definir catálogo inicial de cargos.
- Definir roles iniciales por módulo.
- Definir periodicidad de revisión de accesos.
- Definir tiempo de inactividad permitido.
- Definir controles compensatorios aceptables.
- Definir rol mínimo de cada tipo de usuario.
- Definir si existirán usuarios externos para clientes, proveedores o asesores.

## 22. Aprobación

- Aprobado por: Pendiente
- Fecha: Pendiente
- Observaciones: Este documento es un borrador funcional inicial y no autoriza todavía el desarrollo del módulo.
