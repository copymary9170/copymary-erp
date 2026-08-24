"""Añade la familia técnica de impresoras láser al catálogo de Activos."""
from __future__ import annotations

from src import creative_equipment_knowledge as knowledge


def _laser_profile() -> knowledge.EquipmentProfile:
    return knowledge.EquipmentProfile(
        key="laser_printer",
        family="Papelería creativa",
        equipment="Impresora láser",
        role="Impresión rápida de documentos, formularios, material administrativo y piezas gráficas compatibles con tecnología láser.",
        typical_jobs=(
            "Documentos B/N",
            "documentos a color según modelo",
            "formularios",
            "volantes",
            "material administrativo",
        ),
        wear_parts=(
            "Tóner o cartuchos de tóner",
            "tambor/drum si es independiente",
            "fusor",
            "rodillos de alimentación",
            "banda de transferencia en modelos que la usan",
            "depósito de tóner residual en modelos que lo usan",
        ),
        usage_metric="Páginas impresas",
        maintenance_focus=(
            "vigilar contadores de tóner, tambor y fusor",
            "limpiar recorridos de papel según manual",
            "revisar rodillos si aparecen atascos o alimentación irregular",
            "usar consumibles compatibles con el modelo exacto",
            "no asumir que tóner, tambor y fusor son una sola pieza",
        ),
        electrical_level="Media / pico alto",
        voltage_note="El consumo cambia mucho entre reposo, impresión y calentamiento del fusor; registrar la placa/manual del modelo concreto.",
        electrical_notes=(
            "El fusor necesita calor y puede producir picos de consumo superiores a una impresora de tanque.",
            "No aplicar automáticamente a una láser los valores eléctricos de HP Smart Tank, Epson EcoTank o Canon PIXMA G/MegaTank.",
            "Antes de conectarla a UPS o regulador, verificar que el dispositivo soporte la potencia y los picos indicados por el fabricante.",
        ),
        environment_notes=(
            "Mantener libres las rejillas de ventilación y evitar acumulación de polvo de papel.",
            "Dejar el espacio de ventilación y las zonas calientes indicado por el fabricante.",
        ),
        source_label="Perfil genérico: verificar manual, placa y consumibles del modelo real.",
    )


def activate_laser_printer_profile() -> None:
    """Extiende PROFILES sin duplicar el perfil si el loader se ejecuta más de una vez."""
    if knowledge.profile_by_key("laser_printer") is not None:
        return
    knowledge.PROFILES = (*knowledge.PROFILES, _laser_profile())
