"""Análisis de compras para CopyMary ERP.

Solo lectura: recomienda reposición y compara costos históricos de proveedores
sin crear compras ni modificar inventario.
"""

from __future__ import annotations

from collections import defaultdict

import streamlit as st

from src.components import render_info_card
from src.money import format_money
from src.session_utils import read_list


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _supplier_names(suppliers: list[dict]) -> dict[str, str]:
    return {
        str(item.get("supplier_id", "")): str(item.get("name", "Proveedor"))
        for item in suppliers
    }


def _recommendations(inventory: list[dict]) -> list[dict]:
    rows = []
    for item in inventory:
        available = _num(item.get("available_quantity"))
        minimum = _num(item.get("minimum_stock"))
        if minimum <= 0 or available > minimum:
            continue
        target = max(minimum * 2, minimum)
        suggested = max(target - available, 0.0)
        rows.append({
            "Artículo": str(item.get("name", "Material")),
            "Disponible": available,
            "Mínimo": minimum,
            "Sugerido": suggested,
            "Unidad": str(item.get("unit_name", "unidad")),
            "Prioridad": "Urgente" if available <= 0 else "Reponer",
        })
    return sorted(rows, key=lambda row: (row["Prioridad"] != "Urgente", row["Disponible"] / max(row["Mínimo"], 1)))


def _price_history(purchases: list[dict], suppliers: list[dict]) -> dict[str, list[dict]]:
    names = _supplier_names(suppliers)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for purchase in purchases:
        name = str(purchase.get("material_name", "")).strip()
        if not name:
            continue
        quantity = _num(purchase.get("quantity"))
        unit_cost = _num(purchase.get("unit_cost"))
        if unit_cost <= 0 and quantity > 0:
            unit_cost = _num(purchase.get("total")) / quantity
        if unit_cost <= 0:
            continue
        grouped[name.casefold()].append({
            "Artículo": name,
            "Proveedor": names.get(str(purchase.get("supplier_id", "")), "Sin proveedor"),
            "Costo unitario": unit_cost,
            "Cantidad": quantity,
            "Unidad": str(purchase.get("unit_name", "unidad")),
            "Fecha": str(purchase.get("created_at_utc", ""))[:10],
        })
    return grouped


def render_purchase_analysis() -> None:
    """Renderiza recomendaciones y comparación histórica de proveedores."""
    inventory = read_list("inventory_registry")
    purchases = read_list("purchases_registry")
    suppliers = read_list("suppliers_registry")

    recommendations_tab, comparison_tab = st.tabs(("Recomendaciones de compra", "Comparar proveedores"))

    with recommendations_tab:
        st.markdown("#### Recomendaciones de reposición")
        st.caption("Sugiere una compra cuando la existencia llega al mínimo. El objetivo provisional es recuperar hasta 2× el stock mínimo.")
        rows = _recommendations(inventory)
        if not rows:
            st.success("No hay artículos con reposición sugerida según los mínimos registrados.")
        else:
            urgent = sum(1 for row in rows if row["Prioridad"] == "Urgente")
            metrics = st.columns(3)
            metrics[0].metric("Por reponer", str(len(rows)))
            metrics[1].metric("Agotados", str(urgent))
            metrics[2].metric("Con existencia", str(len(rows) - urgent))
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.info("Estas cantidades son recomendaciones. No crean órdenes ni modifican existencias automáticamente.")

    with comparison_tab:
        st.markdown("#### Comparación de precios históricos")
        history = _price_history(purchases, suppliers)
        comparable = {
            key: rows for key, rows in history.items()
            if len({row["Proveedor"] for row in rows if row["Proveedor"] != "Sin proveedor"}) >= 2
        }
        if not history:
            st.info("Todavía no hay compras con costos unitarios para comparar.")
        else:
            labels = {rows[-1]["Artículo"]: key for key, rows in history.items()}
            selected_label = st.selectbox("Artículo", sorted(labels), key="purchase_analysis_item")
            rows = history[labels[selected_label]]
            latest_by_supplier: dict[str, dict] = {}
            for row in rows:
                supplier = row["Proveedor"]
                previous = latest_by_supplier.get(supplier)
                if previous is None or row["Fecha"] >= previous["Fecha"]:
                    latest_by_supplier[supplier] = row
            comparison = sorted(latest_by_supplier.values(), key=lambda row: row["Costo unitario"])
            best = comparison[0]["Costo unitario"] if comparison else 0.0
            for row in comparison:
                row["Diferencia vs mejor"] = row["Costo unitario"] - best
                row["Diferencia %"] = ((row["Costo unitario"] / best) - 1) * 100 if best > 0 else 0.0
            st.dataframe(comparison, use_container_width=True, hide_index=True)
            if comparison:
                winner = comparison[0]
                st.success(f"Mejor costo registrado: {winner['Proveedor']} · {format_money(winner['Costo unitario'])} por {winner['Unidad']}.")
            if len(comparison) < 2:
                st.warning("Este artículo todavía no tiene precios de al menos dos proveedores; la comparación es limitada.")
            st.caption(f"Artículos con comparación real entre 2+ proveedores: {len(comparable)}")

    render_info_card(
        "Decisión de compra",
        "Las recomendaciones usan mínimos de inventario y la comparación usa costos históricos reales. Antes de comprar, confirma vigencia, presentación, impuestos, envío y disponibilidad con el proveedor.",
        "ANÁLISIS DE COMPRAS",
    )
