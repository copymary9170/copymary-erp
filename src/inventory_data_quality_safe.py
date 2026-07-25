"""Diagnóstico de solo lectura para la calidad de datos de Inventario."""
from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
import streamlit as st

from src import inventory_enterprise


_FIELD_GROUPS = {
    "Código o SKU": ("sku", "code", "codigo", "item_code"),
    "Nombre": ("name", "nombre", "description", "descripcion"),
    "Categoría": ("category", "categoria"),
    "Unidad": ("unit", "unidad", "uom"),
    "Ubicación": ("location", "ubicacion", "warehouse_location"),
    "Proveedor": ("supplier", "proveedor", "supplier_name"),
    "Stock mínimo": ("minimum_stock", "min_stock", "stock_minimo"),
    "Costo": ("cost", "unit_cost", "average_cost", "costo"),
}


def _first_value(row: Mapping[str, object], keys: tuple[str, ...]) -> object:
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def _missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _diagnostic_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        missing_fields = [
            label for label, keys in _FIELD_GROUPS.items()
            if _missing(_first_value(row, keys))
        ]
        result.append({
            "Artículo": _first_value(row, _FIELD_GROUPS["Nombre"]) or f"Registro {index}",
            "Código": _first_value(row, _FIELD_GROUPS["Código o SKU"]) or "Sin código",
            "Campos faltantes": ", ".join(missing_fields) if missing_fields else "Completo",
            "Cantidad faltante": len(missing_fields),
            "Estado": "Completo" if not missing_fields else "Revisar",
        })
    return result


def render_inventory_data_quality() -> None:
    """Muestra un diagnóstico sin modificar ningún registro."""
    rows = inventory_enterprise._items()
    st.subheader("Diagnóstico de datos maestros")
    st.caption(
        "Revisión de solo lectura. Detecta campos vacíos o no registrados; no corrige, "
        "completa ni modifica artículos automáticamente."
    )

    if not rows:
        st.info("No existen artículos para diagnosticar.")
        return

    diagnostic = _diagnostic_rows(rows)
    incomplete = [row for row in diagnostic if row["Estado"] == "Revisar"]
    complete = len(diagnostic) - len(incomplete)

    columns = st.columns(4)
    columns[0].metric("Artículos revisados", len(diagnostic))
    columns[1].metric("Completos", complete)
    columns[2].metric("Por revisar", len(incomplete))
    columns[3].metric("Completitud", f"{(complete / len(diagnostic)) * 100:.0f}%")

    status = st.selectbox("Mostrar", ("Por revisar", "Todos", "Completos"), key="inventory_data_quality_filter")
    if status == "Por revisar":
        visible = incomplete
    elif status == "Completos":
        visible = [row for row in diagnostic if row["Estado"] == "Completo"]
    else:
        visible = diagnostic

    st.dataframe(pd.DataFrame(visible), use_container_width=True, hide_index=True)
    st.info(
        "Los datos deben corregirse desde Catálogo o mediante los controles logísticos "
        "autorizados. Este diagnóstico no cambia existencias, costos ni movimientos."
    )
