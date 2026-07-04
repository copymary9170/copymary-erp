# CopyMary ERP

Sistema ERP empresarial para CopyMary, creado desde una base limpia y modular.

## Objetivo

Centralizar y organizar las áreas principales del negocio sin repetir los problemas estructurales del repositorio anterior.

## Módulos previstos

- Inicio y panel general
- Usuarios, roles y permisos
- Recursos Humanos
- Área Legal
- Ventas y clientes
- Compras y proveedores
- Inventario
- Finanzas
- Producción y servicios
- Reportes
- Configuración

## Principios del proyecto

- Arquitectura modular
- Seguridad desde el inicio
- Cambios pequeños y comprobables
- Separación entre interfaz, lógica y datos
- Documentación de decisiones importantes
- No copiar errores ni archivos innecesarios del prototipo anterior

## Estado actual

La rama `main` contiene una primera interfaz funcional y descriptiva construida con Streamlit.

Actualmente incluye:

- página de Inicio;
- navegación lateral;
- cinco módulos fundacionales;
- métricas generales del proyecto;
- actividad reciente identificada como demostración;
- avisos claros de que todavía no existen operaciones empresariales reales.

Esta etapa no incluye base de datos, autenticación real, formularios operativos ni almacenamiento de información.

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

La aplicación debe mostrar la página de Inicio, las métricas y los cinco módulos descriptivos.

## Limitaciones actuales

- No guarda datos.
- No utiliza base de datos.
- No implementa autenticación.
- No contiene módulos empresariales terminados.
- No debe usarse todavía como sistema de producción.

## Próximo paso recomendado

Verificar la aplicación en Streamlit Community Cloud y corregir únicamente el primer error que aparezca antes de continuar con nuevas funciones.
