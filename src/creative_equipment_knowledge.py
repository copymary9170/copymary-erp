"""Base técnica orientativa para equipos de papelería creativa y sublimación.

Los valores eléctricos de perfiles concretos proceden de fichas/manuales de fabricante.
Para equipos genéricos el ERP exige verificar la placa del equipo: no inventa potencia,
vida útil ni capacidad de circuito. Las recomendaciones de instalación no sustituyen
al fabricante, al código eléctrico local ni a un electricista calificado.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EquipmentProfile:
    key: str
    family: str
    equipment: str
    role: str
    typical_jobs: tuple[str, ...]
    wear_parts: tuple[str, ...]
    usage_metric: str
    maintenance_focus: tuple[str, ...]
    electrical_level: str
    voltage_note: str
    watts_reference: float | None = None
    amps_reference: float | None = None
    electrical_notes: tuple[str, ...] = ()
    environment_notes: tuple[str, ...] = ()
    source_label: str = "Referencia general; verificar placa/manual"
    source_url: str = ""


PROFILES: tuple[EquipmentProfile, ...] = (
    EquipmentProfile(
        "inkjet_tank", "Papelería creativa", "Impresora de tinta continua / EcoTank",
        "Impresión de documentos, stickers, fotografías y papelería personalizada.",
        ("Cabezal", "almohadilla/caja de mantenimiento", "rodillos", "tintas"),
        "Páginas impresas",
        ("test de inyectores", "limpieza solo cuando sea necesaria", "control de rodillos y alimentación"),
        "Baja", "Muchos modelos domésticos son universales 100–240 V; verificar placa.",
        12.0, 0.4,
        ("No necesita tratarse como una carga térmica grande.", "Registrar consumo en operación y reposo por separado cuando el fabricante lo publique."),
        ("Evitar calor directo, humedad condensante y polvo de papel."),
        "Epson ET-2800: 100–240 V, 0.4–0.2 A, aprox. 12 W copiando",
        "https://files.support.epson.com/docid/cpd6/cpd60270/source/spcs/source/specifications/references/et2800_l3260/spex_electrical_spc_et2800_l3260.html",
    ),
    EquipmentProfile(
        "sublimation_printer", "Sublimación", "Impresora dedicada de sublimación",
        "Imprime transfer para textiles y sustratos rígidos preparados para sublimación.",
        ("Cabezal", "tinta de sublimación", "caja/almohadilla de mantenimiento", "rodillos"),
        "Páginas impresas",
        ("test de inyectores", "control de tinta y fecha de apertura", "evitar largos periodos sin uso"),
        "Baja", "Ejemplo Epson SureColor F170: 100–240 V, 50–60 Hz.",
        13.0, 0.4,
        ("La impresora consume poco comparada con la prensa; conviene separar ambos equipos en el inventario eléctrico."),
        ("Epson F170 publica operación 10–35 °C y 20–80% HR sin condensación."),
        "Epson SureColor F170: aprox. 13 W operando; 4.1 W ready; 0.7 W sleep",
        "https://epson.com/For-Work/Printers/Large-Format/SureColor-F170-Dye-Sublimation-Printer/p/C11CJ80201",
    ),
    EquipmentProfile(
        "cutting_plotter", "Papelería creativa", "Plotter de corte de escritorio",
        "Corte de vinil, cartulina, stickers impresos y materiales de manualidades.",
        ("Cuchilla", "tapete/base de corte", "rodillos", "herramientas"),
        "Metros de corte",
        ("limpieza de riel/carro", "revisión de cuchilla", "control del adhesivo del tapete", "calibración print & cut"),
        "Baja", "Ejemplo Silhouette Cameo 5: adaptador DC 24 V / 1.25 A.",
        25.0, None,
        ("Usar el adaptador especificado por el fabricante.", "Registrar adaptador como accesorio crítico reemplazable."),
        ("Cameo 5 publica 10–35 °C y 35–75% HR, sin condensación."),
        "Silhouette Cameo 5: 25 W; adaptador 24 V / 1.25 A",
        "https://www.silhouetteamerica.com/silhouette-cameo5-nqt-1",
    ),
    EquipmentProfile(
        "laminator", "Papelería creativa", "Laminadora / plastificadora térmica",
        "Protección y acabado de tarjetas, portadas, menús, documentos y material impreso.",
        ("Rodillos", "resistencia/calefactor", "sensores", "mecanismo de arrastre"),
        "Metros laminados",
        ("limpiar rodillos según manual", "evitar adhesivo expuesto", "revisar alimentación y temperatura"),
        "Media/Alta", "La potencia cambia mucho según formato; verificar placa. Un modelo Fellowes Voyager 125 publica 120 V / 8.5 A.",
        1100.0, 8.5,
        ("Tratar como equipo térmico: no compartir regleta sobrecargada.", "Enchufe accesible y cable sin daños."),
        ("Mantener líquidos lejos del equipo y del tomacorriente."),
        "Fellowes Voyager 125: 120 V, 8.5 A, 1100 W",
        "https://assets.fellowes.com/manuals/403916_2_NA_Voyager_reader.pdf",
    ),
    EquipmentProfile(
        "heat_press", "Sublimación", "Prensa térmica plana",
        "Transferencia por calor: sublimación, HTV y otros materiales autorizados por el fabricante.",
        ("Resistencia/plato calefactor", "controlador", "relé", "teflón/protector", "amortiguador/resorte"),
        "Planchados",
        ("verificar uniformidad de temperatura", "revisar cable/enchufe", "limpiar plato frío", "control de presión"),
        "Alta", "Modelos 15×15 pueden estar alrededor de 13–15 A a 120 V; verificar siempre la placa.",
        1400.0, 13.0,
        ("Es una carga térmica importante; evitar regletas o extensiones subdimensionadas.", "Registrar si el fabricante exige circuito/disyuntor específico.", "No dimensionar circuito solo con este perfil: usar placa, manual y código local."),
        ("Dejar espacio para apertura y superficies resistentes al calor."),
        "HPN Black Series 15×15: 110–120 V, 1400 W / 13 A",
        "https://heatpressnation.com/products/hpn-black-series-15-x-15-high-pressure-heat-press-machine",
    ),
    EquipmentProfile(
        "mug_press", "Sublimación", "Prensa de tazas / vasos",
        "Sublimación de tazas y recipientes compatibles.",
        ("Resistencia/manta", "controlador", "conectores", "sensores"),
        "Ciclos de prensado",
        ("control de desgaste de manta", "revisión de conectores", "temperatura uniforme"),
        "Media/Alta", "Potencia y voltaje varían por número y tamaño de resistencias; registrar placa.",
        None, None,
        ("No asumir que una prensa de taza consume lo mismo que una plana.", "Registrar cada resistencia como repuesto crítico cuando sea reemplazable."),
        ("Ventilación y superficie resistente al calor."),
    ),
    EquipmentProfile(
        "convection_oven", "Sublimación", "Horno de convección dedicado",
        "Sublimación de tumblers y objetos 3D compatibles; no mezclar con preparación de alimentos.",
        ("Resistencias", "ventilador", "termostato/controlador", "sellos"),
        "Horas de uso",
        ("control de temperatura", "ventilador", "cableado y enchufe", "limpieza interna según materiales usados"),
        "Alta", "Registrar potencia nominal, voltaje y corriente de placa; puede ser una de las mayores cargas del taller.",
        None, None,
        ("Evaluar circuito y simultaneidad con otras cargas térmicas.", "No usar extensiones temporales como instalación permanente."),
        ("Ventilación adecuada y separación de materiales combustibles."),
    ),
    EquipmentProfile(
        "foil_machine", "Papelería creativa", "Aplicadora / estampadora de foil",
        "Foil reactivo al calor, hot stamping o aplicación según el sistema del equipo.",
        ("Rodillo/silicona", "resistencia", "termostato", "fusible"),
        "Estampados de foil",
        ("limpieza de rodillos/plato", "calibración de temperatura", "revisión de presión"),
        "Media/Alta", "Al ser equipo térmico, registrar W/A de placa y tipo de enchufe.",
    ),
    EquipmentProfile(
        "binding_machine", "Papelería creativa", "Anilladora / encuadernadora",
        "Perforación y cierre de espirales, wire-o, canutillo u otros sistemas.",
        ("Punzones", "palancas", "cuchillas", "motor si es eléctrica"),
        "Perforaciones",
        ("limpieza de residuos", "lubricación si el manual lo permite", "control de punzones"),
        "Nula/Baja", "Manual: sin carga eléctrica. Eléctrica: registrar placa del motor.",
    ),
    EquipmentProfile(
        "electric_guillotine", "Papelería creativa", "Guillotina / cortadora eléctrica",
        "Corte repetitivo de papel o pilas dentro de la capacidad del fabricante.",
        ("Cuchilla", "barra de corte", "motor", "sensores/guardas"),
        "Cortes",
        ("afilado/cambio de cuchilla", "guardas y sensores", "lubricación autorizada"),
        "Media/Alta", "Potencia depende mucho del formato y accionamiento; registrar placa y protecciones.",
        None, None,
        ("No anular guardas ni sensores de seguridad.",),
    ),
    EquipmentProfile(
        "laser_engraver", "Papelería creativa", "Láser de grabado/corte",
        "Grabado y corte de materiales expresamente compatibles con la máquina y su extracción.",
        ("Lente", "espejos si aplica", "filtro/extractor", "tubo CO2 o módulo diodo", "correas/rieles"),
        "Horas de uso",
        ("limpieza óptica", "extracción", "alineación si aplica", "refrigeración", "inspección de material permitido"),
        "Variable", "El consumo depende de potencia láser, extractor, bomba/chiller y accesorios: registrarlos como cargas separadas.",
        None, None,
        ("No agrupar láser + extractor + chiller como si fueran una sola carga desconocida.", "Registrar ventilación/extracción como activo auxiliar."),
        ("Extracción adecuada y control de humo según material/manual."),
    ),
    EquipmentProfile(
        "computer", "Soporte", "Computadora de diseño / estación de trabajo",
        "Diseño, RIP, Silhouette Studio/Cricut Design Space, gestión de pedidos y ERP.",
        ("Fuente de poder", "ventiladores", "SSD", "batería si es laptop"),
        "Horas de uso",
        ("limpieza de polvo", "respaldo", "temperaturas", "estado de batería/almacenamiento"),
        "Baja/Media", "Registrar potencia del adaptador/fuente y consumo real si se desea costeo energético.",
        None, None,
        ("Es mejor candidata para UPS que una prensa térmica de alta potencia."),
    ),
    EquipmentProfile(
        "ups_regulator", "Soporte eléctrico", "UPS / regulador / protector de sobretensión",
        "Protección y continuidad para electrónica compatible con su capacidad.",
        ("Batería", "fusible", "ventilador en modelos grandes"),
        "Horas energizado",
        ("prueba de batería", "capacidad disponible", "alarmas", "fecha de reemplazo de batería"),
        "Soporte", "Registrar VA, W máximos, tensión de entrada/salida y tipo de tomas.",
        None, None,
        ("No conectar automáticamente equipos térmicos de alta potencia a un UPS sin validar capacidad y manual.", "Registrar qué activos protege para evitar sobrecarga lógica."),
    ),
)


def profile_by_key(key: str) -> EquipmentProfile | None:
    return next((item for item in PROFILES if item.key == key), None)


def electrical_current(watts: float, voltage: float) -> float:
    """Corriente aproximada I=P/V para una carga resistiva/estimación simple."""
    if watts <= 0 or voltage <= 0:
        return 0.0
    return watts / voltage


def load_percent(amps: float, circuit_amps: float) -> float:
    if amps <= 0 or circuit_amps <= 0:
        return 0.0
    return amps / circuit_amps * 100.0
