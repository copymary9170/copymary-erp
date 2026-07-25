"""Resumen seguro de prioridades para hallazgos de Inventario.

Esta vista no corrige datos. Solo agrupa riesgos y recomienda el módulo donde
corresponde revisar cada situación.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

import streamlit as st

from src import inventory_enterprise


def _value(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return default


def _number(row: dict[str, Any], *keys: str) -> float | None:
    value = _value(row, *keys)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _label(row: dict[str, Any]) -> str:
    name = str(_value(row, "name", "nombre", "item_name", default="Artículo sin nombre"))
    code = str(_value(row, "sku", "code", "codigo", "código", default="Sin código"))
    return f"{name} · {code}"


def _findings(rows: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    rows = list(rows)
    normalized_codes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        code = str(_value(row, "sku", "code", "codigo", "código", default="")).strip().casefold()
        if code:
            normalized_codes[code].append(row)

    duplicate_ids = {
        id(row)
        for matches in normalized_codes.values()
        if len(matches) > 1
        for row in matches
    }

    findings: list[dict[str, str]] = []
    for row in rows:
        label = _label(row)
        cost = _number(row, "average_cost", "avg_cost", "cost", "costo", "unit_cost")
        minimum = _number(row, "minimum_stock", "min_stock", "stock_min", "stock_minimo", "stock_mínimo")
        maximum = _number(row, "maximum_stock", "max_stock", "stock_max", "stock_maximo", "stock_máximo")
        physical = _number(row, "stock", "physical_stock", "quantity", "existence", "existencia")

        if id(row) in duplicate_ids:
            findings.append({"Prioridad": "Alta", "Artículo": label, "Hallazgo": "Código o SKU duplicado", "Acción recomendada": "Revisar y corregir el identificador en Catálogo."})
        if cost is not None and cost < 0:
            findings.append({"Prioridad": "Crítica", "Artículo": label, "Hallazgo": "Costo negativo", "Acción recomendada": "Revisar el origen del costo en Compras y Recepción antes de valorar existencias."})
        if physical is not None and physical < 0:
            findings.append({"Prioridad": "Crítica", "Artículo": label, "Hallazgo": "Existencia física negativa", "Acción recomendada": "Revisar movimientos, reservas y el último conteo físico."})
        if minimum is not None and minimum < 0:
            findings.append({"Prioridad": "Alta", "Artículo": label, "Hallazgo": "Stock mínimo negativo", "Acción recomendada": "Corregir la política de reposición en Catálogo."})
        if minimum is not None and maximum is not None and minimum > maximum:
            findings.append({"Prioridad": "Alta", "Artículo": label, "Hallazgo": "Stock mínimo superior al máximo", "Acción recomendada": "Revisar los límites de reposición en Catálogo."})
        if physical is not None and maximum is not None and physical > maximum:
            findings.append({"Prioridad": "Media", "Artículo": label, "Hallazgo": "Existencia superior al máximo", "Acción recomendada": "Revisar compras pendientes y reducir temporalmente la reposición."})
    return findings


def render_inventory_priority_summary() -> None:
    """Muestra prioridades y acciones sugeridas sin modificar registros."""
    rows = inventory_enterprise._items()
    findings = _findings(rows)

    st.divider()
    st.subheader("Prioridades de revisión")
    st.caption("Resumen orientativo de solo lectura. Ninguna acción se ejecuta automáticamente.")

    counts = Counter(item["Prioridad"] for item in findings)
    columns = st.columns(4)
    columns[0].metric("Hallazgos", len(findings))
    columns[1].metric("Críticos", counts.get("Crítica", 0))
    columns[2].metric("Altos", counts.get("Alta", 0))
    columns[3].metric("Medios", counts.get("Media", 0))

    if not findings:
        st.success("No se detectaron prioridades adicionales con las reglas actuales.")
        return

    priority_order = ["Crítica", "Alta", "Media"]
    selected = st.selectbox("Filtrar por prioridad", ["Todas", *priority_order], key="inventory_priority_filter")
    filtered = findings if selected == "Todas" else [item for item in findings if item["Prioridad"] == selected]

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.info(
        "Orden sugerido: primero costos o existencias negativas; después códigos duplicados y límites incoherentes; "
        "por último, excesos sobre el máximo. Las correcciones deben hacerse en Catálogo, Compras, Recepción, "
        "Movimientos o Conteo físico según la recomendación mostrada."
    )
