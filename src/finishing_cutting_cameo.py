"""Cola de corte en Silhouette Cameo para CopyMary ERP."""

from __future__ import annotations

from src.finishing_jobs import STAGE_CUTTING
from src.finishing_view import render_finishing_stage


def render_finishing_cutting_cameo() -> None:
    render_finishing_stage(
        stage=STAGE_CUTTING,
        title="Corte en Cameo",
        subtitle="Recibe trabajos para cortar (vinil, stickers, plantillas) y registra uso de la Silhouette Cameo.",
        material_keywords=("vinil", "vinilo", "sticker", "adhesivo", "cartulina", "acetato", "imantado"),
        material_label="Material a cortar",
        asset_keywords=("cameo", "silhouette"),
        asset_label="Silhouette Cameo",
        footer_note="El material se busca en Inventario por nombre o categoría (vinil, sticker, adhesivo, cartulina). El uso de máquina se suma al activo cuyo nombre contenga \"Cameo\" o \"Silhouette\" en Activos.",
    )
