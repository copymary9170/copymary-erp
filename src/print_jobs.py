"""Confirmación real de trabajos de impresión para CopyMary ERP.

`print_cost_analyzer_v3.py` calcula un costo y un precio sugerido, pero hasta
ahora sólo generaba un reporte descargable: el stock de papel proyectado y el
uso de la impresora nunca se escribían de vuelta al ERP. Este módulo es lo
que falta para que "Analizar y calcular" (una cotización) se convierta en
"Confirmar trabajo impreso" (una transacción real):

- descuenta las hojas de papel realmente consumidas del ítem de Inventario
  usado, dejando un movimiento de salida trazable;
- incrementa el contador de páginas (`current_units`) del activo impresora,
  para que la depreciación y "vida restante" reflejen el uso real;
- guarda el trabajo en `print_jobs`, con snapshot del desglose de costos, para
  poder auditar después cotizado vs. producido y para poder enviarlo a un
  módulo de acabado (Plastificado, Corte en Cameo, Sublimado).

Sigue el mismo patrón de persistencia en `st.session_state` que el resto del
ERP (ver `session_utils.py` y `session_backup.py`).
"""

from __future__ import annotations

from uuid import uuid4

import streamlit as st

from src import session_backup
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save

# Claves candidatas donde puede vivir el ítem de inventario, en el mismo
# orden que usa `print_cost_data_bridge._inventory_rows()`.
_INVENTORY_KEYS = ("inventory_items", "inventory_registry", "products", "catalog_products")

# Nombres de campo de cantidad disponible, en orden de preferencia, iguales
# a los que ya lee `print_cost_data_bridge.paper_inventory()`.
_QUANTITY_FIELDS = ("available_quantity", "stock", "quantity", "current_stock")


def _activate_backup() -> None:
    for section, label in (
        ("print_jobs", "Trabajos de impresión confirmados"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = (
        "general_settings",
        *session_backup.LIST_SECTIONS,
        *session_backup.DICT_SECTIONS,
    )


_activate_backup()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def deduct_inventory_item(item_id: str, quantity: float, reason: str) -> bool:
    """Descuenta `quantity` del ítem `item_id` en el primer registro de
    Inventario donde aparezca, y deja un movimiento de salida.

    Devuelve `True` si encontró el ítem y descontó; `False` si no lo encontró
    en ninguna de las listas conocidas (no rompe el flujo del llamador, pero
    permite advertir al usuario).
    """
    if quantity <= 0:
        return False
    for key in _INVENTORY_KEYS:
        rows = _rows(key)
        found = False
        updated_rows: list[dict] = []
        previous_quantity = 0.0
        resulting_quantity = 0.0
        item_name = "Material"
        for row in rows:
            current_id = str(row.get("item_id") or row.get("product_id") or row.get("sku") or row.get("id") or row.get("name") or "")
            if not found and current_id == str(item_id):
                found = True
                item_name = str(row.get("name") or row.get("product_name") or row.get("description") or "Material")
                field = next((f for f in _QUANTITY_FIELDS if f in row), _QUANTITY_FIELDS[0])
                previous_quantity = _num(row.get(field))
                resulting_quantity = max(previous_quantity - quantity, 0.0)
                row = dict(row)
                row[field] = resulting_quantity
            updated_rows.append(row)
        if found:
            _save(key, updated_rows)
            movements = _rows("inventory_movements")
            movements.append({
                "movement_id": uuid4().hex[:10],
                "created_at_utc": _now(),
                "item_id": str(item_id),
                "item_name": item_name,
                "movement_type": "Salida",
                "quantity": quantity,
                "reason": reason,
                "previous_quantity": previous_quantity,
                "resulting_quantity": resulting_quantity,
            })
            _save("inventory_movements", movements)
            return True
    return False


def increment_asset_usage(asset_id: str, units: float) -> bool:
    """Incrementa `current_units` del activo `asset_id` en `units` páginas.

    Opera directamente sobre `st.session_state['assets_registry']` (misma
    fuente que usa `assets.py`) para no depender de funciones privadas de
    otro módulo. Devuelve `True` si encontró y actualizó el activo.
    """
    if units <= 0:
        return False
    raw_assets = st.session_state.get("assets_registry", [])
    updated: list[dict] = []
    found = False
    for raw in raw_assets:
        row = dict(raw) if isinstance(raw, dict) else dict(vars(raw))
        if not found and str(row.get("asset_id")) == str(asset_id):
            found = True
            row["current_units"] = int(_num(row.get("current_units")) + units)
        updated.append(row)
    if found:
        st.session_state.assets_registry = updated
    return found


def confirm_print_job(result: dict, *, paper_item_id: str, sheets: float, asset_id: str, printed_pages: int) -> dict:
    """Registra un trabajo de impresión como transacción real:

    - descuenta `sheets` del ítem de papel `paper_item_id` en Inventario;
    - incrementa `printed_pages` en el contador de uso del activo `asset_id`;
    - guarda el resultado completo (desglose de costos incluido) en
      `print_jobs`, con estado inicial `Confirmado` y sin envío a acabado.

    Devuelve el registro del trabajo creado, incluyendo su `job_id`, para que
    el llamador pueda ofrecer de inmediato "Enviar a acabado".
    """
    paper_deducted = deduct_inventory_item(
        paper_item_id, sheets, f"Trabajo de impresión {result.get('archivo', '')}".strip()
    )
    asset_updated = increment_asset_usage(asset_id, printed_pages)

    jobs = _rows("print_jobs")
    job = {
        "job_id": f"IMP-{uuid4().hex[:8].upper()}",
        "created_at_utc": _now(),
        "status": "Confirmado",
        "paper_deducted": paper_deducted,
        "asset_updated": asset_updated,
        **result,
    }
    jobs.append(job)
    _save("print_jobs", jobs)
    return job


def recent_jobs(limit: int = 100) -> list[dict]:
    return list(reversed(_rows("print_jobs")[-limit:]))


def job_by_id(job_id: str) -> dict | None:
    for job in _rows("print_jobs"):
        if str(job.get("job_id")) == str(job_id):
            return job
    return None
