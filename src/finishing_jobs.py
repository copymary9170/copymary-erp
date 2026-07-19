"""Motor compartido de acabados para CopyMary ERP.

Un trabajo de impresión confirmado (`print_jobs.py`) puede necesitar uno o
más procesos posteriores: plastificado, corte en la Silhouette Cameo, o
sublimado sobre un blanco (taza, camisa, etc.). En vez de tres módulos que
reinventen la misma cola, la misma lógica de consumo de material y el mismo
uso de máquina, este módulo centraliza:

- la creación de un trabajo de acabado a partir de un trabajo de impresión
  (o de forma independiente, para acabados que no parten de una impresión,
  por ejemplo cortar un vinil que se compró ya cortado en rollo);
- la cola de pendientes por etapa;
- completar un trabajo, lo que consume material real de Inventario y
  registra uso de la máquina correspondiente en Activos, igual que hace
  `print_jobs.py` para el papel y la impresora.

Cada módulo de acabado (`finishing_laminating.py`, `finishing_cutting_cameo.py`,
`finishing_sublimation.py`) es una vista delgada sobre estas funciones.
"""

from __future__ import annotations

from uuid import uuid4

import streamlit as st

from src import session_backup
from src.print_cost_data_bridge import _inventory_rows
from src.print_jobs import deduct_inventory_item, increment_asset_usage
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save

STAGE_LAMINATING = "Plastificado"
STAGE_CUTTING = "Corte en Cameo"
STAGE_SUBLIMATION = "Sublimado"
STAGE_FOIL = "Aplicación de foil"
STAGE_BINDING = "Encuadernación"
STAGE_ASSEMBLY = "Ensamblaje"
STAGE_DTF_VINYL = "DTF / Vinil textil"
STAGES = (STAGE_LAMINATING, STAGE_CUTTING, STAGE_SUBLIMATION, STAGE_FOIL, STAGE_BINDING, STAGE_ASSEMBLY, STAGE_DTF_VINYL)

STATUSES = ("Pendiente", "En proceso", "Completado", "Cancelado")


def _activate_backup() -> None:
    for section, label in (("finishing_jobs", "Trabajos de acabado"),):
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


def create_job(stage: str, *, source_job_id: str = "", description: str = "", quantity: float = 1.0, requested_by: str = "") -> dict:
    """Crea un trabajo de acabado en estado `Pendiente`.

    `source_job_id` referencia el `job_id` de `print_jobs` cuando el acabado
    parte de un trabajo impreso; queda vacío para acabados independientes.
    """
    if stage not in STAGES:
        raise ValueError(f"Etapa de acabado desconocida: {stage}")
    jobs = _rows("finishing_jobs")
    job = {
        "finishing_id": f"AC-{uuid4().hex[:8].upper()}",
        "stage": stage,
        "source_job_id": source_job_id,
        "description": description.strip(),
        "quantity": _num(quantity, 1.0),
        "requested_by": requested_by.strip() or "Sistema",
        "status": "Pendiente",
        "created_at_utc": _now(),
        "material_item_id": "",
        "material_used": 0.0,
        "asset_id": "",
        "completed_at_utc": "",
        "note": "",
    }
    jobs.append(job)
    _save("finishing_jobs", jobs)
    return job


def jobs_for_stage(stage: str, *, include_done: bool = False) -> list[dict]:
    jobs = _rows("finishing_jobs")
    if include_done:
        return [job for job in jobs if job.get("stage") == stage]
    return [job for job in jobs if job.get("stage") == stage and job.get("status") not in {"Completado", "Cancelado"}]


def _update_job(finishing_id: str, updates: dict) -> dict | None:
    jobs = _rows("finishing_jobs")
    changed = None
    result = []
    for row in jobs:
        current = dict(row)
        if str(current.get("finishing_id")) == str(finishing_id):
            current.update(updates)
            changed = current
        result.append(current)
    _save("finishing_jobs", result)
    return changed


def start_job(finishing_id: str) -> dict | None:
    return _update_job(finishing_id, {"status": "En proceso"})


def cancel_job(finishing_id: str, note: str = "") -> dict | None:
    return _update_job(finishing_id, {"status": "Cancelado", "note": note.strip()})


def complete_job(
    finishing_id: str,
    *,
    material_item_id: str = "",
    material_quantity: float = 0.0,
    asset_id: str = "",
    machine_units: float = 0.0,
    note: str = "",
) -> dict | None:
    """Marca un trabajo de acabado como `Completado`.

    Si se indica `material_item_id`, descuenta `material_quantity` de
    Inventario real (misma lógica que usa `print_jobs.py` para el papel). Si
    se indica `asset_id`, incrementa el uso de esa máquina en Activos.
    """
    material_deducted = False
    if material_item_id and material_quantity > 0:
        material_deducted = deduct_inventory_item(
            material_item_id, material_quantity, f"Acabado {finishing_id}"
        )
    asset_updated = False
    if asset_id and machine_units > 0:
        asset_updated = increment_asset_usage(asset_id, machine_units)
    return _update_job(
        finishing_id,
        {
            "status": "Completado",
            "material_item_id": material_item_id,
            "material_used": material_quantity,
            "material_deducted": material_deducted,
            "asset_id": asset_id,
            "asset_updated": asset_updated,
            "note": note.strip(),
            "completed_at_utc": _now(),
        },
    )


def material_options(*keywords: str) -> list[dict]:
    """Ítems de Inventario cuyo nombre o categoría contiene alguna de
    `keywords` (p. ej. "vinil", "laminad", "sublim", "taza"). Misma fuente y
    normalización que usa `print_cost_data_bridge.paper_inventory()`, pero
    genérica en vez de limitada a papeles.
    """
    lowered = [keyword.casefold() for keyword in keywords]
    result: list[dict] = []
    seen: set[str] = set()
    for row in _inventory_rows():
        name = str(row.get("name") or row.get("product_name") or row.get("description") or row.get("title") or "").strip()
        category = str(row.get("category") or row.get("type") or row.get("family") or "").strip()
        searchable = f"{name} {category}".casefold()
        if not name or not any(keyword in searchable for keyword in lowered):
            continue
        cost = _num(row.get("unit_cost") or row.get("cost") or row.get("average_cost") or row.get("purchase_cost"))
        stock = _num(row.get("stock") if row.get("stock") is not None else row.get("quantity") if row.get("quantity") is not None else row.get("current_stock"), 0.0)
        item_id = str(row.get("item_id") or row.get("product_id") or row.get("sku") or row.get("id") or name)
        dedupe_key = item_id.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append({
            "item_id": item_id, "name": name, "category": category,
            "unit_cost": cost, "stock": stock,
            "unit": str(row.get("unit") or row.get("measurement_unit") or "unidad"),
            "valid_cost": cost > 0, "available": stock > 0,
        })
    return sorted(result, key=lambda item: item["name"].casefold())


def assets_by_keyword(*keywords: str) -> list[dict]:
    """Activos cuyo nombre o categoría contiene alguna de `keywords`

    (insensible a mayúsculas/acentos simples). Usado para ofrecer, por
    ejemplo, sólo la Silhouette Cameo en el módulo de corte, o sólo la
    impresora de sublimación en el módulo de sublimado.
    """
    raw_assets = st.session_state.get("assets_registry", [])
    lowered = [keyword.casefold() for keyword in keywords]
    result = []
    for raw in raw_assets:
        row = dict(raw) if isinstance(raw, dict) else dict(vars(raw))
        haystack = f"{row.get('name', '')} {row.get('category', '')}".casefold()
        if any(keyword in haystack for keyword in lowered):
            result.append(row)
    return result
