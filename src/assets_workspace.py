"""Workspace ejecutivo para Activos y mantenimiento.

No reemplaza el registro histórico existente: lo organiza y añade una capa de
lectura gerencial sobre `src.assets` y `src.machine_maintenance`.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from src import assets as legacy_assets
from src import machine_maintenance
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import read_list


def _maintenance_cost_by_asset() -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in read_list("asset_maintenance_log"):
        asset_id = str(row.get("asset_id") or "")
        totals[asset_id] = totals.get(asset_id, 0.0) + float(row.get("cost", 0.0) or 0.0)
    return totals


def _replacement_priority(asset) -> str:
    if asset.status in ("Fuera de servicio", "Dado de baja"):
        return "Crítica"
    if asset.usage_percent >= 90:
        return "Alta"
    if asset.usage_percent >= 75 or asset.warranty_status == "Vencida":
        return "Media"
    return "Normal"


def _asset_health(asset) -> int:
    score = 100
    if asset.status == "En mantenimiento":
        score -= 25
    elif asset.status == "Fuera de servicio":
        score -= 60
    elif asset.status in ("Dado de baja", "Vendido"):
        score -= 100
    if asset.usage_percent >= 90:
        score -= 30
    elif asset.usage_percent >= 75:
        score -= 15
    if asset.warranty_status == "Vencida":
        score -= 10
    elif asset.warranty_status == "Por vencer":
        score -= 5
    return max(score, 0)


def _dashboard() -> None:
    assets = legacy_assets._get_assets()
    maintenance_costs = _maintenance_cost_by_asset()
    total_cost = sum(a.acquisition_cost for a in assets)
    book_value = sum(a.remaining_value for a in assets)
    maintenance_total = sum(maintenance_costs.values())
    available = sum(a.available_for_quoting for a in assets)

    render_page_header(
        "Centro de Activos",
        "Estado, valor, vida útil, garantías, mantenimiento y reemplazo de tus equipos en una sola vista.",
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equipos registrados", len(assets))
    c2.metric("Disponibles para cotizar", available)
    c3.metric("Valor en libros", format_money(book_value))
    c4.metric("Mantenimiento acumulado", format_money(maintenance_total))

    if not assets:
        st.info("Todavía no hay activos registrados. Entra en Registro para agregar el primero.")
        return

    high_risk = [a for a in assets if _replacement_priority(a) in ("Crítica", "Alta")]
    expiring = [a for a in assets if a.warranty_status == "Por vencer"]
    unavailable = [a for a in assets if a.status not in ("Activo",)]
    if high_risk or expiring or unavailable:
        st.markdown("### Alertas")
        if high_risk:
            st.error("Reemplazo prioritario: " + ", ".join(a.name for a in high_risk))
        if expiring:
            st.warning("Garantía por vencer: " + ", ".join(a.name for a in expiring))
        if unavailable:
            st.warning("Equipos no operativos: " + ", ".join(f"{a.name} ({a.status})" for a in unavailable))

    st.markdown("### Salud del parque de equipos")
    rows = []
    for asset in sorted(assets, key=lambda x: (_asset_health(x), -x.usage_percent)):
        rows.append({
            "Equipo": asset.name,
            "Categoría": asset.category,
            "Estado": asset.status,
            "Salud": f"{_asset_health(asset)}%",
            "Uso": f"{asset.usage_percent:.1f}%",
            "Valor pendiente": asset.remaining_value,
            "Mantenimiento": maintenance_costs.get(asset.asset_id, 0.0),
            "Garantía": asset.warranty_status,
            "Reemplazo": _replacement_priority(asset),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("### Lectura financiera")
    depreciated = max(total_cost - book_value, 0.0)
    c1, c2, c3 = st.columns(3)
    c1.metric("Inversión histórica", format_money(total_cost))
    c2.metric("Depreciación acumulada", format_money(depreciated))
    c3.metric("Valor recuperable pendiente", format_money(book_value))
    render_info_card(
        "Qué mirar primero",
        "Prioriza equipos con uso alto, garantía vencida, mantenimiento creciente o estado fuera de servicio. "
        "El objetivo no es reemplazar por antigüedad solamente, sino evitar que una falla detenga producción.",
        "DECISIÓN OPERATIVA",
    )


def _replacement_plan() -> None:
    assets = legacy_assets._get_assets()
    maintenance_costs = _maintenance_cost_by_asset()
    st.subheader("Plan de reemplazo")
    st.caption("Ordena los equipos por riesgo operativo y valor pendiente sin borrar su historial.")
    if not assets:
        st.info("No hay activos registrados.")
        return

    rows = []
    for asset in assets:
        remaining_units = max(asset.lifetime_units - asset.current_units, 0)
        rows.append({
            "Equipo": asset.name,
            "Prioridad": _replacement_priority(asset),
            "Estado": asset.status,
            "Uso %": round(asset.usage_percent, 1),
            "Unidades restantes": remaining_units,
            "Valor pendiente": round(asset.remaining_value, 2),
            "Mantenimiento acumulado": round(maintenance_costs.get(asset.asset_id, 0.0), 2),
            "Garantía": asset.warranty_status,
        })
    priority_order = {"Crítica": 0, "Alta": 1, "Media": 2, "Normal": 3}
    rows.sort(key=lambda r: (priority_order.get(r["Prioridad"], 9), -r["Uso %"]))
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("#### Reserva orientativa de reposición")
    replacement_horizon_months = st.number_input("Meses para formar la reserva", min_value=1, max_value=120, value=24, step=1)
    candidates = [a for a in assets if _replacement_priority(a) in ("Crítica", "Alta", "Media") and a.status != "Vendido"]
    target = sum(max(a.remaining_value, 0.0) for a in candidates)
    monthly = target / int(replacement_horizon_months) if replacement_horizon_months else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric("Equipos a vigilar", len(candidates))
    c2.metric("Valor pendiente considerado", format_money(target))
    c3.metric("Reserva mensual orientativa", format_money(monthly))
    st.caption("Es una referencia de planificación, no un asiento contable ni una obligación automática.")


def _maintenance_summary() -> None:
    st.subheader("Mantenimiento y garantías")
    assets = legacy_assets._get_assets()
    logs = read_list("asset_maintenance_log")
    costs = _maintenance_cost_by_asset()
    if assets:
        rows = []
        for asset in assets:
            asset_logs = [x for x in logs if x.get("asset_id") == asset.asset_id]
            last_event = max((str(x.get("event_date") or x.get("recorded_at_utc", "")) for x in asset_logs), default="")
            rows.append({
                "Equipo": asset.name,
                "Estado": asset.status,
                "Garantía": asset.warranty_status,
                "Último mantenimiento": last_event[:10] if last_event else "—",
                "Eventos": len(asset_logs),
                "Costo acumulado": round(costs.get(asset.asset_id, 0.0), 2),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No hay activos registrados.")

    st.divider()
    st.markdown("#### Planes preventivos")
    st.caption("Debajo sigue disponible el módulo completo de mantenimiento preventivo, incluidos planes por fecha o por uso.")
    machine_maintenance.render_machine_maintenance()


def render_assets_workspace() -> None:
    section = st.radio(
        "Área de Activos",
        ("Resumen", "Registro y ficha", "Mantenimiento", "Reemplazo"),
        horizontal=True,
        label_visibility="collapsed",
        key="assets_workspace_section",
    )
    st.divider()
    if section == "Resumen":
        _dashboard()
    elif section == "Registro y ficha":
        legacy_assets.render_assets()
    elif section == "Mantenimiento":
        _maintenance_summary()
    else:
        _replacement_plan()
