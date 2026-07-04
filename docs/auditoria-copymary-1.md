# Auditoría inicial de `copymary-1`

Fecha: 2026-07-04

## Conclusión

En los archivos revisados no aparece un error de sintaxis evidente que impida arrancar la aplicación. El problema principal de `copymary-1` es que quedó como una demostración muy básica, con páginas estáticas, estructura incompleta y promesas de módulos que realmente no existen.

No se copiará este repositorio completo. Solo se reutilizarán ideas o fragmentos después de revisarlos.

## Hallazgos principales

### 1. La aplicación anuncia un módulo que no existe

`app.py` indica que el menú permite entrar a Legal, RRHH, Procesos y Dashboard, pero dentro de `pages/` no aparece una página funcional de RRHH.

**Riesgo:** el sistema comunica una capacidad que todavía no fue construida.

**Regla para el nuevo ERP:** ningún módulo se anunciará como disponible hasta que tenga su página, navegación, permisos y pruebas mínimas.

### 2. Los módulos son solo texto estático

Legal y Procesos únicamente muestran títulos y listas. No tienen formularios, validaciones, almacenamiento, edición, búsqueda, filtros ni gestión documental.

**Riesgo:** parece un ERP por su interfaz, pero todavía no realiza operaciones empresariales.

**Regla para el nuevo ERP:** cada módulo deberá definir primero sus funciones reales, datos, formularios, estados, permisos y criterios de aceptación.

### 3. No existe separación de responsabilidades

La interfaz está escrita directamente en cada archivo de página. No hay capas separadas para:

- lógica de negocio;
- acceso a datos;
- modelos;
- validaciones;
- servicios;
- seguridad;
- componentes reutilizables.

**Riesgo:** al crecer, el código se vuelve repetido, difícil de probar y difícil de corregir.

**Regla para el nuevo ERP:** separar presentación, dominio, servicios e infraestructura desde el inicio.

### 4. No hay autenticación, usuarios, roles ni permisos

Cualquier persona que acceda a la aplicación podría ver las mismas páginas. No existe control por cargo, departamento o nivel de autorización.

**Riesgo:** exposición de información laboral, financiera, legal o empresarial.

**Regla para el nuevo ERP:** construir autenticación y autorización antes de incorporar información sensible.

### 5. No hay base de datos ni persistencia

El Dashboard crea una tabla fija dentro del propio código. Los datos desaparecen o deben modificarse manualmente en los archivos.

**Riesgo:** no existe historial, trazabilidad ni información empresarial real.

**Regla para el nuevo ERP:** definir modelo de datos, migraciones, respaldos y auditoría antes de crear formularios definitivos.

### 6. Dependencias sin versiones

`requirements.txt` contiene solamente `streamlit` y `pandas`, sin versiones fijadas.

**Riesgo:** una actualización futura puede cambiar el comportamiento o romper el despliegue.

**Regla para el nuevo ERP:** usar versiones controladas y actualizar dependencias de forma intencional.

### 7. No hay pruebas automáticas

No existen pruebas para navegación, formularios, permisos, cálculos ni datos.

**Riesgo:** cada cambio puede dañar otra parte del sistema sin que se detecte.

**Regla para el nuevo ERP:** cada función crítica deberá incorporar pruebas antes de considerarse terminada.

### 8. El Dashboard no usa datos reales

Los módulos, estados y prioridades están escritos manualmente en un DataFrame.

**Riesgo:** el tablero puede mostrar información diferente al estado verdadero del sistema.

**Regla para el nuevo ERP:** los indicadores deberán calcularse a partir de una fuente de datos real y verificable.

## Qué sí puede conservarse

- El nombre CopyMary ERP.
- Streamlit como opción inicial de interfaz, sujeto a validación técnica.
- La idea de navegación por módulos.
- Los nombres generales Legal, RRHH, Procesos y Dashboard.
- La intención de partir de una base limpia.

## Qué no debe copiarse directamente

- La estructura plana actual.
- Las páginas estáticas como módulos terminados.
- El Dashboard con datos escritos manualmente.
- Dependencias sin versiones.
- La ausencia de autenticación y permisos.
- La creación simultánea de muchos módulos vacíos.

## Orden recomendado para `copymary-erp`

1. Definir alcance y módulos de la primera versión.
2. Diseñar usuarios, roles y permisos.
3. Diseñar el modelo de datos.
4. Elegir arquitectura y estructura de carpetas.
5. Crear una aplicación mínima que arranque correctamente.
6. Construir un solo módulo completo de principio a fin.
7. Añadir pruebas y documentación.
8. Repetir el patrón para los siguientes módulos.

## Criterio de éxito

La nueva versión no será considerada funcional solo porque muestre páginas. Un módulo estará listo cuando permita realizar una tarea real, valide los datos, respete permisos, guarde cambios, mantenga trazabilidad y tenga pruebas mínimas.
