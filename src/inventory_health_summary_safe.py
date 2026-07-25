"""Resumen ejecutivo de salud de Inventario, de solo lectura.

Consolida calidad de datos, consistencia y prioridades sin modificar registros.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import streamlit as st

from src import inventory_enterprise
from src.inventory_priority_summary_safe import _findings


_REQUIRED_FIELDS: tuple[tuple[str, ...], ...] = (
    ("sku", "code", "codigo", "código"),
    ("name", "nombre", "item_name"),
    ("category", "categoria", "categoría"),
    ("unit", "unidad", "uom"),
    ("location", "ubicacion", "ubicación"),
    ("supplier", "proveedor", "supplier_name"),
    ("minimum_stock", "min_stock", "stock_min", "stock_minimo", "stock_mínimo"),
    ("average_cost", "avg_cost", "cost", "costo", "unit_cost"),
)


def _has_value(row: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(row.get(key) not in (None, "") for key in keys)


def _completion(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 100.0
    total_checks = len(rows) * len(_REQUIRED_FIELDS)
    completed = sum(_has_value(row, keys) for row in rows for keys in _REQUIRED_FIELDS)
    return (completed / total_checks) * 100


def _health_score(completion: float, counts: Counter[str], total_items: int) -> int:
    """Calcula un índice orientativo y explicable entre 0 y 100."""
    denominator = max(total_items, 1)
    critical_penalty = min(40.0, (counts.get("Crítica", 0) / denominator) * 40)
    high_penalty = min(25.0, (counts.get("Alta", 0) / denominator) * 25)
    medium_penalty = min(10.0, (counts.get("Media", 0) / denominator) * 10)
    quality_penalty = (100.0 - completion) * 0.25
    return max(0, min(100, round(100 - critical_penalty - high_penalty - medium_penalty - quality_penalty)))


def _status(score: int) -> str:
    if score >= 90:
        return "Saludable"
    if score >= 75:
        return "Estable con revisiones"
    if score >= 60:
        return "Atención requerida"
    return "Riesgo elevado"


def render_inventory_health_summary() -> None:
    """Muestra indicadores consolidados sin modificar el inventario."""
    rows = list(inventory_enterprise._items())
    findings = _findings(rows)
    counts = Counter(item["Prioridad"] for item in findings)
    completion = _completion(rows)
    score = _health_score(completion, counts, len(rows))

    st.divider()
    st.subheader("Resumen ejecutivo de salud del inventario")
    st.caption(
        "Indicadores orientativos de solo lectura. El índice no altera costos, existencias ni políticas de reposición."
    )

    columns = st.columns(5)
    columns[0].metric("Índice de salud", f"{score}/100")
    columns[1].metric("Estado", _status(score))
    columns[2].metric("Datos completos", f"{completion:.1f}%")
    columns[3].metric("Artículos", len(rows))
    columns[4].metric("Hallazgos", len(findings))

    priority_columns = st.columns(3)
    priority_columns[0].metric("Críticos", counts.get("Crítica", 0))
    priority_columns[1].metric("Altos", counts.get("Alta", 0))
    priority_columns[2].metric("Medios", counts.get("Media", 0))

    st.progress(score / 100, text=f"Salud general: {_status(score)}")

    if counts.get("Crítica", 0):
        st.error("Prioridad inmediata: revisar costos o existencias negativas antes de valorar, comprar o despachar.")
    elif counts.get("Alta", 0):
        st.warning("Prioridad próxima: corregir códigos duplicados y políticas de mínimos o máximos.")
    elif findings:
        st.info("Prioridad preventiva: revisar excesos sobre máximos y ajustar temporalmente la reposición.")
    else:
        st.success("No se detectaron hallazgos con las reglas actuales.")

    st.caption(
        "El índice combina completitud de datos y hallazgos críticos, altos y medios. Es un apoyo de gestión, no una valoración contable."
    )
