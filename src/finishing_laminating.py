"""Cola de plastificado para CopyMary ERP."""

from __future__ import annotations

from src.finishing_jobs import STAGE_LAMINATING
from src.finishing_view import render_finishing_stage


def render_finishing_laminating() -> None:
    render_finishing_stage(
        stage=STAGE_LAMINATING,
        title="Plastificado",
        subtitle="Recibe trabajos impresos y descuenta el laminado/bolsa usada desde Inventario.",
        material_keywords=("laminad", "plastific", "bolsa termica", "bolsa térmica", "mica"),
        material_label="Laminado / bolsa usada",
        asset_keywords=("plastificad", "laminad"),
        asset_label="Máquina de plastificar",
        footer_note="El material se busca en Inventario por nombre o categoría (laminado, bolsa térmica, mica). Si no existe el ítem, complétalo en Inventario para que el descuento sea automático.",
    )
