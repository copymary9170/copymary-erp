"""Activa los módulos de la separación Catálogo / Compras / Inventario:
Catálogo de artículos (Fase 1) y Recepción de mercancía (Fase 3)."""
from src import app_shell
from src.catalog_items import render_catalog_items
from src.goods_receipt import render_goods_receipt


def activate_catalog_items() -> None:
    app_shell.FUNCTIONAL_MODULES["Catálogo de artículos"] = render_catalog_items
    app_shell.FUNCTIONAL_MODULES["Recepción de mercancía"] = render_goods_receipt
    try:
        from src import top_navigation_app
        top_navigation_app.DESCRIPTIONS["Catálogo de artículos"] = (
            "Definición permanente de artículos: tipo, unidad, dimensiones y gramaje."
        )
        top_navigation_app.DESCRIPTIONS["Recepción de mercancía"] = (
            "Confirma lo recibido; solo lo aceptado aumenta el inventario."
        )
    except (ImportError, KeyError):
        pass
