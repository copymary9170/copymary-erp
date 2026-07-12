"""Lectura segura de datos ERP para el costeo de impresión."""
from __future__ import annotations

from statistics import mean
import streamlit as st

from src import assets
from src.session_utils import read_list


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def printer_assets() -> list[dict]:
    specs = read_list("printer_asset_specs")
    spec_by_asset = {str(row.get("asset_id")): row for row in specs if row.get("active", True)}
    logs = read_list("asset_maintenance_logs")
    result = []
    for asset in assets._get_assets():
        if "impres" not in asset.category.casefold() and "impres" not in asset.name.casefold():
            continue
        spec = spec_by_asset.get(str(asset.asset_id), {})
        maintenance_costs = [_num(row.get("cost")) for row in logs if str(row.get("asset_id")) == str(asset.asset_id) and _num(row.get("cost")) > 0]
        result.append({
            "asset_id": asset.asset_id,
            "name": asset.name,
            "printer_cost": asset.acquisition_cost,
            "life_pages": asset.lifetime_units,
            "current_pages": asset.current_units,
            "remaining_pages": max(asset.lifetime_units - asset.current_units, 0),
            "depreciation_per_page": asset.depreciation_per_unit,
            "head_cost": _num(spec.get("head_cost"), 100.0),
            "head_life": int(_num(spec.get("head_life"), 30000)),
            "color_yield": int(_num(spec.get("color_yield"), 6000)),
            "black_yield": int(_num(spec.get("black_yield"), 12000)),
            "ink_c": _num(spec.get("ink_c"), 19.0),
            "ink_m": _num(spec.get("ink_m"), 19.0),
            "ink_y": _num(spec.get("ink_y"), 19.0),
            "ink_k": _num(spec.get("ink_k"), 19.0),
            "ppm": _num(spec.get("ppm"), 8.0),
            "watts": _num(spec.get("watts"), 18.0),
            "maintenance_page": _num(spec.get("maintenance_page"), (mean(maintenance_costs) / max(asset.current_units, 1)) if maintenance_costs else 0.003),
            "complete": bool(spec),
        })
    return result


def _inventory_rows() -> list[dict]:
    rows: list[dict] = []
    for key in ("inventory_items", "inventory_registry", "products", "catalog_products"):
        value = st.session_state.get(key, [])
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    return rows


def paper_inventory() -> list[dict]:
    """Devuelve únicamente papeles válidos registrados en Inventario.

    Cada elemento conserva su identificador, nombre, costo unitario y stock. No se
    crean valores predeterminados: si el artículo no existe en Inventario, no puede
    seleccionarse en el costeo.
    """
    paper_tokens = (
        "papel", "bond", "oficio", "carta", "fotograf", "opalina", "adhesivo",
        "sticker", "cartulina", "acetato", "imantado", "lustrillo", "construccion",
    )
    result: list[dict] = []
    seen: set[str] = set()
    for row in _inventory_rows():
        name = str(row.get("name") or row.get("product_name") or row.get("description") or row.get("title") or "").strip()
        category = str(row.get("category") or row.get("type") or row.get("family") or "").strip()
        searchable = f"{name} {category}".casefold()
        if not name or not any(token in searchable for token in paper_tokens):
            continue
        cost = _num(row.get("unit_cost") or row.get("cost") or row.get("average_cost") or row.get("purchase_cost"))
        stock = _num(row.get("stock") if row.get("stock") is not None else row.get("quantity") if row.get("quantity") is not None else row.get("current_stock"), 0.0)
        item_id = str(row.get("item_id") or row.get("product_id") or row.get("sku") or row.get("id") or name)
        dedupe_key = item_id.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append({
            "item_id": item_id,
            "name": name,
            "category": category or "Papel",
            "unit_cost": cost,
            "stock": stock,
            "unit": str(row.get("unit") or row.get("measurement_unit") or "hoja"),
            "valid_cost": cost > 0,
            "available": stock > 0,
        })
    return sorted(result, key=lambda item: item["name"].casefold())


def paper_costs() -> dict[str, float]:
    """Compatibilidad para otros módulos; deriva costos solo de Inventario."""
    return {item["name"]: item["unit_cost"] for item in paper_inventory() if item["valid_cost"]}


def business_defaults() -> dict:
    settings = st.session_state.get("general_settings", {})
    if not isinstance(settings, dict):
        settings = {}
    return {
        "electricity_kwh": _num(settings.get("electricity_kwh") or settings.get("electricity_cost_kwh"), 0.10),
        "labor_hour": _num(settings.get("labor_hour") or settings.get("hourly_labor_cost"), 2.50),
        "overhead_pct": _num(settings.get("overhead_pct") or settings.get("indirect_cost_pct"), 10.0),
        "margin_pct": _num(settings.get("default_margin_pct") or settings.get("margin_pct"), 40.0),
    }
