"""Clasificación de materiales que pueden usarse como soporte de impresión.

Los artículos existentes se consideran imprimibles por defecto para mantener
compatibilidad. Solo se excluyen cuando el usuario los marca expresamente como
no imprimibles en el Catálogo de artículos.
"""
from __future__ import annotations

from typing import Any, Callable

from src.session_utils import read_list, save_list

PRINTABLE_OVERRIDES_KEY = "printable_material_overrides"


def _text(value: object) -> str:
    return str(value or "").strip().casefold()


def _identity(record: Any) -> tuple[str, str, str]:
    if isinstance(record, dict):
        return (
            _text(record.get("item_id") or record.get("id") or record.get("material_id")),
            _text(record.get("sku") or record.get("code")),
            _text(record.get("name") or record.get("material") or record.get("material_name") or record.get("product_name")),
        )
    return (
        _text(getattr(record, "item_id", "")),
        _text(getattr(record, "sku", "")),
        _text(getattr(record, "name", "")),
    )


def _overrides() -> list[dict]:
    return [dict(row) for row in read_list(PRINTABLE_OVERRIDES_KEY) if isinstance(row, dict)]


def is_printable(record: Any) -> bool:
    """Devuelve la clasificación del artículo; los registros antiguos son True."""
    if isinstance(record, dict) and "printable" in record:
        return bool(record.get("printable"))
    item_id, sku, name = _identity(record)
    for row in _overrides():
        row_id, row_sku, row_name = _identity(row)
        if item_id and row_id == item_id:
            return bool(row.get("printable", True))
        if sku and row_sku == sku:
            return bool(row.get("printable", True))
        if name and row_name == name:
            return bool(row.get("printable", True))
    return True


def set_printable(record: Any, printable: bool) -> None:
    """Guarda una decisión explícita sin modificar el registro maestro."""
    item_id, sku, name = _identity(record)
    rows = _overrides()
    updated = False
    for row in rows:
        row_id, row_sku, row_name = _identity(row)
        if (item_id and row_id == item_id) or (sku and row_sku == sku) or (name and row_name == name):
            row.update({"item_id": item_id, "sku": sku, "name": name, "printable": bool(printable)})
            updated = True
            break
    if not updated:
        rows.append({"item_id": item_id, "sku": sku, "name": name, "printable": bool(printable)})
    save_list(PRINTABLE_OVERRIDES_KEY, rows)


def filter_printable(records: list[Any]) -> list[Any]:
    return [record for record in records if is_printable(record)]


def activate_printing_filters() -> None:
    """Aplica el filtro al puente de datos usado por el módulo de impresión."""
    try:
        from src import print_cost_data_bridge as bridge
    except Exception:
        return

    for function_name in ("paper_inventory", "printable_inventory"):
        original: Callable[..., Any] | None = getattr(bridge, function_name, None)
        if original is None or getattr(original, "_copymary_printable_filter", False):
            continue

        def filtered(*args, _original=original, **kwargs):
            result = _original(*args, **kwargs)
            return filter_printable(result) if isinstance(result, list) else result

        filtered._copymary_printable_filter = True  # type: ignore[attr-defined]
        setattr(bridge, function_name, filtered)
