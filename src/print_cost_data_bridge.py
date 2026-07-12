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


def paper_costs() -> dict[str, float]:
    candidates = []
    for key in ("inventory_items", "products", "catalog_products", "inventory_registry"):
        value = st.session_state.get(key, [])
        if isinstance(value, list):
            candidates.extend(row for row in value if isinstance(row, dict))
    result = {}
    aliases = {
        "bond": "Bond carta 75 g", "oficio": "Bond oficio 75 g", "fotografico mate": "Fotográfico mate",
        "fotografico brillante": "Fotográfico brillante", "opalina": "Opalina", "adhesivo": "Adhesivo",
    }
    for row in candidates:
        name = str(row.get("name") or row.get("product_name") or row.get("description") or "").casefold()
        cost = _num(row.get("unit_cost") or row.get("cost") or row.get("average_cost"))
        if cost <= 0:
            continue
        for token, label in aliases.items():
            if token in name:
                result[label] = cost
    return result


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
