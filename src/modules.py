"""Contenido descriptivo de los módulos disponibles en la primera interfaz."""

from typing import TypedDict


class ModuleInfo(TypedDict):
    description: str
    status: str
    objective: str
    planned_functions: list[str]
    dependencies: list[str]


MODULES: dict[str, ModuleInfo] = {
    "Gobierno Empresarial": {
        "description": "Define la estructura de dirección, decisiones, políticas y responsabilidades de CopyMary.",
        "status": "Blueprint inicial creado. Desarrollo funcional pendiente.",
        "objective": "Establecer reglas claras para dirigir, controlar y hacer crecer la empresa de forma ordenada.",
        "planned_functions": [
            "Estructura organizacional y responsabilidades",
            "Políticas empresariales",
            "Registro de decisiones y aprobaciones",
            "Seguimiento de objetivos estratégicos",
        ],
        "dependencies": ["Usuarios, Roles y Permisos", "Auditoría y Trazabilidad"],
    },
    "Seguridad": {
        "description": "Agrupa los controles previstos para proteger el sistema, la información y las operaciones.",
        "status": "Blueprint inicial creado. Desarrollo funcional pendiente.",
        "objective": "Reducir riesgos de acceso indebido, pérdida de información y uso inseguro del ERP.",
        "planned_functions": [
            "Políticas de seguridad",
            "Control de sesiones",
            "Gestión futura de credenciales",
            "Alertas y revisión de eventos de seguridad",
        ],
        "dependencies": ["Usuarios, Roles y Permisos", "Auditoría y Trazabilidad"],
    },
    "Usuarios, Roles y Permisos": {
        "description": "Definirá quién puede ingresar al sistema y qué acciones podrá realizar cada persona.",
        "status": "Blueprint inicial creado. Desarrollo funcional pendiente.",
        "objective": "Aplicar acceso mínimo necesario y separar responsabilidades dentro de la empresa.",
        "planned_functions": [
            "Gestión de usuarios",
            "Definición de roles",
            "Matriz de permisos",
            "Asignación y revisión de accesos",
        ],
        "dependencies": ["Seguridad", "Auditoría y Trazabilidad"],
    },
    "Auditoría y Trazabilidad": {
        "description": "Permitirá conocer qué ocurrió, quién realizó una acción y cuándo se produjo.",
        "status": "Blueprint inicial creado. Desarrollo funcional pendiente.",
        "objective": "Proteger la memoria operativa del negocio y facilitar revisiones internas.",
        "planned_functions": [
            "Registro de acciones relevantes",
            "Historial de cambios",
            "Consulta de eventos",
            "Reportes de trazabilidad",
        ],
        "dependencies": ["Usuarios, Roles y Permisos", "Configuración General"],
    },
    "Configuración General": {
        "description": "Centralizará los parámetros comunes utilizados por los demás módulos del ERP.",
        "status": "Primera función temporal disponible durante la sesión.",
        "objective": "Evitar configuraciones dispersas y mantener criterios uniformes en todo el sistema.",
        "planned_functions": [
            "Datos generales de la empresa",
            "Preferencias del sistema",
            "Catálogos y parámetros comunes",
            "Configuración regional y formatos",
        ],
        "dependencies": ["Gobierno Empresarial", "Auditoría y Trazabilidad"],
    },
    "Activos": {
        "description": "Registra temporalmente equipos productivos y calcula su depreciación por unidad.",
        "status": "Primera función temporal disponible durante la sesión.",
        "objective": "Controlar la inversión en equipos y reservar fondos para su reemplazo futuro.",
        "planned_functions": [
            "Registro de máquinas y equipos",
            "Depreciación por unidad producida",
            "Seguimiento de uso estimado",
            "Reserva para reposición de activos",
        ],
        "dependencies": ["Configuración General", "Costeo", "Producción"],
    },
    "Costeo": {
        "description": "Calcula costos y precios orientativos usando la configuración y los activos registrados.",
        "status": "Primera función temporal conectada con Configuración General y Activos.",
        "objective": "Evitar precios improvisados y asegurar que cada venta cubra costos, reposición y ganancia.",
        "planned_functions": [
            "Costos directos por unidad",
            "Costos indirectos prorrateados",
            "Depreciación del activo utilizado",
            "Precio orientativo y ganancia estimada",
        ],
        "dependencies": ["Configuración General", "Activos", "Inventario", "Producción"],
    },
}
