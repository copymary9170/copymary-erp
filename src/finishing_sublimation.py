"""Cola de sublimado para CopyMary ERP."""

from __future__ import annotations

from src.finishing_jobs import STAGE_SUBLIMATION
from src.finishing_view import render_finishing_stage


def render_finishing_sublimation() -> None:
    render_finishing_stage(
        stage=STAGE_SUBLIMATION,
        title="Sublimado",
        subtitle="Recibe trabajos impresos en papel de sublimación y registra el blanco usado (taza, camisa, etc.) y la prensa.",
        material_keywords=("sublim", "taza", "blanco textil", "franela", "playera", "camisa"),
        material_label="Blanco / papel de sublimación usado",
        asset_keywords=("sublimac", "prensa"),
        asset_label="Impresora/prensa de sublimación",
        footer_note="El material se busca en Inventario por nombre o categoría (sublimación, taza, blanco textil). El uso de máquina se suma al activo cuyo nombre contenga \"Sublimación\" o \"Prensa\" en Activos.",
    )
