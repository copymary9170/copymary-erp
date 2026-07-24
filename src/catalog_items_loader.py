"""Activa los módulos de la separación Catálogo / Compras / Inventario:
Catálogo de artículos (Fase 1) y Recepción de mercancía (Fase 3)."""

from src.catalog_items import render_catalog_items
from src.goods_receipt import render_goods_receipt

__all__ = ["render_catalog_items", "render_goods_receipt"]
