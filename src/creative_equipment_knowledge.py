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
        key="inkjet_tank",
        family="Papelería creativa",
        equipment="Impresora de tinta continua / EcoTank",
        role="Impresión de documentos, stickers, fotografías y papelería personalizada.",
        typical_jobs=("Documentos", "stickers", "fotografías", "tarjetas", "papelería personalizada"),
        wear_parts=("Cabezal", "almohadilla/caja de mantenimiento", "rodillos", "tintas"),
        usage_metric="Páginas impresas",
        maintenance_focus=("test de inyectores", "limpieza solo cuando sea necesaria", "control de rodillos y alimentación"),
        electrical_level="Baja",
        voltage_note="Muchos modelos domésticos son universales 100–240 V; verificar placa.",
        watts_reference=12.0,
        amps_reference=0.4,
        electrical_notes=("No necesita tratarse como una carga térmica grande.", "Registrar consumo en operación y reposo por separado cuando el fabricante lo publique."),
        environment_notes=("Evitar calor directo, humedad condensante y polvo de papel.",),
        source_label="Epson ET-2800: 100–240 V, 0.4–0.2 A, aprox. 12 W copiando",
        source_url="https://files.support.epson.com/docid/cpd6/cpd60270/source/spcs/source/specifications/references/et2800_l3260/spex_electrical_spc_et2800_l3260.html",
    ),
    EquipmentProfile(
        key="sublimation_printer",
        family="Sublimación",
        equipment="Impresora dedicada de sublimación",
        role="Imprime transfer para textiles y sustratos rígidos preparados para sublimación.",
        typical_jobs=("Textiles", "tazas", "tumblers", "placas", "productos rígidos sublimables"),
        wear_parts=("Cabezal", "tinta de sublimación", "caja/almohadilla de mantenimiento", "rodillos"),
        usage_metric="Páginas impresas",
        maintenance_focus=("test de inyectores", "control de tinta y fecha de apertura", "evitar largos periodos sin uso"),
        electrical_level="Baja",
        voltage_note="Ejemplo Epson SureColor F170: 100–240 V, 50–60 Hz.",
        watts_reference=13.0,
        amps_reference=0.4,
        electrical_notes=("La impresora consume poco comparada con la prensa; conviene separar ambos equipos en el inventario eléctrico.",),
        environment_notes=("Epson F170 publica operación 10–35 °C y 20–80% HR sin condensación.",),
        source_label="Epson SureColor F170: aprox. 13 W operando; 4.1 W ready; 0.7 W sleep",
        source_url="https://epson.com/For-Work/Printers/Large-Format/SureColor-F170-Dye-Sublimation-Printer/p/C11CJ80201",
    ),
    EquipmentProfile(
        key="cutting_plotter",
        family="Papelería creativa",
        equipment="Plotter de corte de escritorio",
        role="Corte de vinil, cartulina, stickers impresos y materiales de manualidades.",
        typical_jobs=("Vinil adhesivo", "HTV", "cartulina", "stickers print & cut", "plantillas"),
        wear_parts=("Cuchilla", "tapete/base de corte", "rodillos", "herramientas"),
        usage_metric="Metros de corte",
        maintenance_focus=("limpieza de riel/carro", "revisión de cuchilla", "control del adhesivo del tapete", "calibración print & cut"),
        electrical_level="Baja",
        voltage_note="Ejemplo Silhouette Cameo 5: adaptador DC 24 V / 1.25 A.",
        watts_reference=25.0,
        electrical_notes=("Usar el adaptador especificado por el fabricante.", "Registrar adaptador como accesorio crítico reemplazable."),
        environment_notes=("Cameo 5 publica 10–35 °C y 35–75% HR, sin condensación.",),
        source_label="Silhouette Cameo 5: 25 W; adaptador 24 V / 1.25 A",
        source_url="https://www.silhouetteamerica.com/silhouette-cameo5-nqt-1",
    ),
    EquipmentProfile(
        key="laminator",
        family="Papelería creativa",
        equipment="Laminadora / plastificadora térmica",
        role="Protección y acabado de tarjetas, portadas, menús, documentos y material impreso.",
        typical_jobs=("Tarjetas", "portadas", "menús", "documentos", "señalización pequeña"),
        wear_parts=("Rodillos", "resistencia/calefactor", "sensores", "mecanismo de arrastre"),
        usage_metric="Metros laminados",
        maintenance_focus=("limpiar rodillos según manual", "evitar adhesivo expuesto", "revisar alimentación y temperatura"),
        electrical_level="Media/Alta",
        voltage_note="La potencia cambia mucho según formato; verificar placa. Un modelo Fellowes Voyager 125 publica 120 V / 8.5 A.",
        watts_reference=1100.0,
        amps_reference=8.5,
        electrical_notes=("Tratar como equipo térmico: no compartir regleta sobrecargada.", "Enchufe accesible y cable sin daños."),
        environment_notes=("Mantener líquidos lejos del equipo y del tomacorriente.",),
        source_label="Fellowes Voyager 125: 120 V, 8.5 A, 1100 W",
        source_url="https://assets.fellowes.com/manuals/403916_2_NA_Voyager_reader.pdf",
    ),
    EquipmentProfile(
        key="heat_press",
        family="Sublimación",
        equipment="Prensa térmica plana",
        role="Transferencia por calor: sublimación, HTV y otros materiales autorizados por el fabricante.",
        typical_jobs=("Franelas", "bolsas", "mousepads", "placas planas", "HTV"),
        wear_parts=("Resistencia/plato calefactor", "controlador", "relé", "teflón/protector", "amortiguador/resorte"),
        usage_metric="Planchados",
        maintenance_focus=("verificar uniformidad de temperatura", "revisar cable/enchufe", "limpiar plato frío", "control de presión"),
        electrical_level="Alta",
        voltage_note="Modelos 15×15 pueden estar alrededor de 13–15 A a 120 V; verificar siempre la placa.",
        watts_reference=1400.0,
        amps_reference=13.0,
        electrical_notes=("Es una carga térmica importante; evitar regletas o extensiones subdimensionadas.", "Registrar si el fabricante exige circuito/disyuntor específico.", "No dimensionar circuito solo con este perfil: usar placa, manual y código local."),
        environment_notes=("Dejar espacio para apertura y superficies resistentes al calor.",),
        source_label="HPN Black Series 15×15: 110–120 V, 1400 W / 13 A",
        source_url="https://heatpressnation.com/products/hpn-black-series-15-x-15-high-pressure-heat-press-machine",
    ),
    EquipmentProfile(
        key="mug_press",
        family="Sublimación",
        equipment="Prensa de tazas / vasos",
        role="Sublimación de tazas y recipientes compatibles.",
        typical_jobs=("Tazas", "mugs", "vasos", "recipientes compatibles"),
        wear_parts=("Resistencia/manta", "controlador", "conectores", "sensores"),
        usage_metric="Ciclos de prensado",
        maintenance_focus=("control de desgaste de manta", "revisión de conectores", "temperatura uniforme"),
        electrical_level="Media/Alta",
        voltage_note="Potencia y voltaje varían por número y tamaño de resistencias; registrar placa.",
        electrical_notes=("No asumir que una prensa de taza consume lo mismo que una plana.", "Registrar cada resistencia como repuesto crítico cuando sea reemplazable."),
        environment_notes=("Ventilación y superficie resistente al calor.",),
    ),
    EquipmentProfile(
        key="convection_oven",
        family="Sublimación",
        equipment="Horno de convección dedicado",
        role="Sublimación de tumblers y objetos 3D compatibles; no mezclar con preparación de alimentos.",
        typical_jobs=("Tumblers", "vasos 3D", "objetos sublimables compatibles"),
        wear_parts=("Resistencias", "ventilador", "termostato/controlador", "sellos"),
        usage_metric="Horas de uso",
        maintenance_focus=("control de temperatura", "ventilador", "cableado y enchufe", "limpieza interna según materiales usados"),
        electrical_level="Alta",
        voltage_note="Registrar potencia nominal, voltaje y corriente de placa; puede ser una de las mayores cargas del taller.",
        electrical_notes=("Evaluar circuito y simultaneidad con otras cargas térmicas.", "No usar extensiones temporales como instalación permanente."),
        environment_notes=("Ventilación adecuada y separación de materiales combustibles.",),
    ),
    EquipmentProfile(
        key="foil_machine",
        family="Papelería creativa",
        equipment="Aplicadora / estampadora de foil",
        role="Foil reactivo al calor, hot stamping o aplicación según el sistema del equipo.",
        typical_jobs=("Tarjetas", "portadas", "invitaciones", "etiquetas", "acabados decorativos"),
        wear_parts=("Rodillo/silicona", "resistencia", "termostato", "fusible"),
        usage_metric="Estampados de foil",
        maintenance_focus=("limpieza de rodillos/plato", "calibración de temperatura", "revisión de presión"),
        electrical_level="Media/Alta",
        voltage_note="Al ser equipo térmico, registrar W/A de placa y tipo de enchufe.",
    ),
    EquipmentProfile(
        key="binding_machine",
        family="Papelería creativa",
        equipment="Anilladora / encuadernadora",
        role="Perforación y cierre de espirales, wire-o, canutillo u otros sistemas.",
        typical_jobs=("Cuadernos", "agendas", "manuales", "catálogos", "calendarios"),
        wear_parts=("Punzones", "palancas", "cuchillas", "motor si es eléctrica"),
        usage_metric="Perforaciones",
        maintenance_focus=("limpieza de residuos", "lubricación si el manual lo permite", "control de punzones"),
        electrical_level="Nula/Baja",
        voltage_note="Manual: sin carga eléctrica. Eléctrica: registrar placa del motor.",
    ),
    EquipmentProfile(
        key="electric_guillotine",
        family="Papelería creativa",
        equipment="Guillotina / cortadora eléctrica",
        role="Corte repetitivo de papel o pilas dentro de la capacidad del fabricante.",
        typical_jobs=("Corte de resmas", "tarjetas", "volantes", "portadas", "acabado de bloques"),
        wear_parts=("Cuchilla", "barra de corte", "motor", "sensores/guardas"),
        usage_metric="Cortes",
        maintenance_focus=("afilado/cambio de cuchilla", "guardas y sensores", "lubricación autorizada"),
        electrical_level="Media/Alta",
        voltage_note="Potencia depende mucho del formato y accionamiento; registrar placa y protecciones.",
        electrical_notes=("No anular guardas ni sensores de seguridad.",),
    ),
    EquipmentProfile(
        key="laser_engraver",
        family="Papelería creativa",
        equipment="Láser de grabado/corte",
        role="Grabado y corte de materiales expresamente compatibles con la máquina y su extracción.",
        typical_jobs=("Grabado", "corte de MDF/acrílico compatible", "señalización", "personalización"),
        wear_parts=("Lente", "espejos si aplica", "filtro/extractor", "tubo CO2 o módulo diodo", "correas/rieles"),
        usage_metric="Horas de uso",
        maintenance_focus=("limpieza óptica", "extracción", "alineación si aplica", "refrigeración", "inspección de material permitido"),
        electrical_level="Variable",
        voltage_note="El consumo depende de potencia láser, extractor, bomba/chiller y accesorios: registrarlos como cargas separadas.",
        electrical_notes=("No agrupar láser + extractor + chiller como si fueran una sola carga desconocida.", "Registrar ventilación/extracción como activo auxiliar."),
        environment_notes=("Extracción adecuada y control de humo según material/manual.",),
    ),
    EquipmentProfile(
        key="computer",
        family="Soporte",
        equipment="Computadora de diseño / estación de trabajo",
        role="Diseño, RIP, software de corte, gestión de pedidos y ERP.",
        typical_jobs=("Diseño", "preparación de archivos", "RIP", "gestión del ERP", "control de equipos"),
        wear_parts=("Fuente de poder", "ventiladores", "SSD", "batería si es laptop"),
        usage_metric="Horas de uso",
        maintenance_focus=("limpieza de polvo", "respaldo", "temperaturas", "estado de batería/almacenamiento"),
        electrical_level="Baja/Media",
        voltage_note="Registrar potencia del adaptador/fuente y consumo real si se desea costeo energético.",
        electrical_notes=("Es mejor candidata para UPS que una prensa térmica de alta potencia.",),
    ),
    EquipmentProfile(
        key="ups_regulator",
        family="Soporte eléctrico",
        equipment="UPS / regulador / protector de sobretensión",
        role="Protección y continuidad para electrónica compatible con su capacidad.",
        typical_jobs=("Protección de PC", "protección de impresoras compatibles", "continuidad del ERP/red"),
        wear_parts=("Batería", "fusible", "ventilador en modelos grandes"),
        usage_metric="Horas energizado",
        maintenance_focus=("prueba de batería", "capacidad disponible", "alarmas", "fecha de reemplazo de batería"),
        electrical_level="Soporte",
        voltage_note="Registrar VA, W máximos, tensión de entrada/salida y tipo de tomas.",
        electrical_notes=("No conectar automáticamente equipos térmicos de alta potencia a un UPS sin validar capacidad y manual.", "Registrar qué activos protege para evitar sobrecarga lógica."),
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
