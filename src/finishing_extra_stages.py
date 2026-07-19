"""Etapas de acabado adicionales del taller: foil, encuadernación, ensamblaje
y DTF/vinil textil.

Mismo patrón que `finishing_laminating.py` / `finishing_cutting_cameo.py` /
`finishing_sublimation.py`: cada etapa es una capa delgada sobre
`finishing_view.render_finishing_stage`, que ya resuelve la cola de
pendientes, el consumo real de material de Inventario y el registro de uso
de máquina en Activos. Aquí solo se declaran la etapa, las palabras clave de
material/máquina y los textos de la página.
"""

from __future__ import annotations

from src.finishing_jobs import STAGE_ASSEMBLY, STAGE_BINDING, STAGE_DTF_VINYL, STAGE_FOIL
from src.finishing_view import render_finishing_stage


def render_finishing_foil() -> None:
    render_finishing_stage(
        stage=STAGE_FOIL,
        title="Aplicación de foil",
        subtitle="Estampado de foil sobre impresiones: descuenta el rollo de foil de Inventario y suma uso de la estampadora o laminadora.",
        material_keywords=("foil",),
        material_label="Rollo / lámina de foil",
        asset_keywords=("foil", "estampad", "lamin", "plastific"),
        asset_label="Estampadora o laminadora",
        footer_note=(
            "El foil reactivo se aplica pasando la impresión (tóner) con la lámina por la laminadora; "
            "el foil de estampado en caliente usa la estampadora. En ambos casos el material sale de "
            "Inventario y el uso de la máquina alimenta su mantenimiento."
        ),
    )


def render_finishing_binding() -> None:
    render_finishing_stage(
        stage=STAGE_BINDING,
        title="Encuadernación",
        subtitle="Anillado y encuadernado: descuenta espirales, tapas y portadas de Inventario y suma uso de la anilladora.",
        material_keywords=("espiral", "anillo", "tapa", "portada", "encuadern", "wire"),
        material_label="Espiral / tapa / portada",
        asset_keywords=("anillad", "encuadernad"),
        asset_label="Anilladora / encuadernadora",
        footer_note=(
            "Cada encuadernado consume espiral y tapas reales de Inventario, y las perforaciones "
            "suman uso a la anilladora para su mantenimiento preventivo."
        ),
    )


def render_finishing_assembly() -> None:
    render_finishing_stage(
        stage=STAGE_ASSEMBLY,
        title="Ensamblaje",
        subtitle="Armado final de productos (toppers, cajas, recordatorios, kits): descuenta empaques e insumos de armado de Inventario.",
        material_keywords=("empaque", "bolsa", "cinta", "pega", "silicon", "palito", "base", "caja", "lazo"),
        material_label="Empaque / insumo de armado",
        asset_keywords=("ensambl", "armado"),
        asset_label="Equipo de ensamblaje (opcional)",
        footer_note=(
            "El ensamblaje suele ser trabajo manual: lo importante es descontar los insumos reales "
            "(bolsas, cintas, bases, silicón) para que el costo del producto final no los ignore."
        ),
    )


def render_finishing_dtf_vinyl() -> None:
    render_finishing_stage(
        stage=STAGE_DTF_VINYL,
        title="DTF / Vinil textil",
        subtitle="Transferencia a la prenda: descuenta el film DTF o vinil textil de Inventario y suma planchados a la prensa.",
        material_keywords=("dtf", "vinil", "film", "pelicula", "película", "transfer"),
        material_label="Film DTF / vinil textil",
        asset_keywords=("prensa", "plancha", "térmic", "termic"),
        asset_label="Prensa / plancha térmica",
        footer_note=(
            "Un trabajo DTF impreso (Análisis de impresión, tecnología 'DTF') llega aquí para el "
            "planchado final sobre la prenda; el vinil textil cortado en la Cameo también. Cada "
            "planchado suma uso a la prensa para su mantenimiento preventivo."
        ),
    )
