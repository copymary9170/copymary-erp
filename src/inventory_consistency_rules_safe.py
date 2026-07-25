"""Reglas de consistencia de Inventario en modo de solo lectura."""
from __future__ import annotations

from collections import Counter
from typing import Any

import streamlit as st

from src import inventory_enterprise


def _first(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return default


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _analyze(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    codes = [str(_first(row, "codigo", "sku", "code", default="")).strip() for row in rows]
    duplicates = {code for code, count in Counter(codes).items() if code and count > 1}
    findings: list[dict[str, Any]] = []

    for row in rows:
        code = str(_first(row, "codigo", "sku", "code", default="")).strip()
        name = str(_first(row, "nombre", "name", "articulo", default="Sin nombre"))
        cost = _number(_first(row, "costo", "costo_unitario", "cost", default=0))
        minimum = _number(_first(row, "stock_minimo", "minimo", "minimum_stock", default=0))
        physical = _number(_first(row, "existencia", "stock", "cantidad", "physical_stock", default=0))
        maximum = _number(_first(row, "stock_maximo", "maximo", "maximum_stock"))
        issues: list[str] = []

        if code in duplicates:
            issues.append("Código o SKU duplicado")
        if cost is not None and cost < 0:
            issues.append("Costo negativo")
        if minimum is not None and minimum < 0:
            issues.append("Stock mínimo negativo")
        if physical is not None and physical < 0:
            issues.append("Existencia física negativa")
        if minimum is not None and maximum is not None and minimum > maximum:
            issues.append("Stock mínimo superior al máximo")
        if physical is not None and maximum is not None and maximum >= 0 and physical > maximum:
            issues.append("Existencia superior al máximo definido")

        if issues:
            findings.append({
                "Código / SKU": code or "Sin código",
                "Artículo": name,
                "Hallazgos": "; ".join(issues),
                "Existencia física": physical,
                "Stock mínimo": minimum,
                "Stock máximo": maximum,
                "Costo": cost,
            })
    return findings


def render_inventory_consistency_rules() -> None:
    """Muestra anomalías potenciales sin alterar ningún registro."""
    rows = inventory_enterprise._items()
    findings = _analyze(rows)

    st.divider()
    st.subheader("Reglas de consistencia")
    st.caption("Diagnóstico de solo lectura. Los hallazgos deben revisarse antes de corregir datos en los módulos autorizados.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Artículos revisados", len(rows))
    c2.metric("Con hallazgos", len(findings))
    c3.metric("Sin hallazgos", max(len(rows) - len(findings), 0))

    if not findings:
        st.success("No se detectaron códigos duplicados, valores negativos ni mínimos incoherentes.")
        return

    st.warning("Se detectaron datos que podrían afectar compras, reposición, valoración o disponibilidad.")
    st.dataframe(findings, use_container_width=True, hide_index=True)
