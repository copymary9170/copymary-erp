"""Capa visible para confirmar y acceder a controles enterprise de reversos."""

from collections import Counter

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.production_reversals_enterprise import render_production_reversals_enterprise


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render_production_reversals_visible() -> None:
    """Muestra primero las mejoras nuevas y luego el flujo completo del módulo."""
    requests = _rows("production_reversal_requests")
    reworks = _rows("production_rework_orders")
    batches = _rows("production_batches")
    sales = _rows("sales_registry")
    counts = Counter(str(item.get("status", "Pendiente")) for item in requests)
    executed = [item for item in requests if item.get("status") == "Ejecutado"]
    recovered = sum(_num(item.get("recovered_cost")) for item in executed)
    lost = sum(_num(item.get("lost_cost")) for item in executed)

    render_page_header(
        "Reversos de producción · versión enterprise activa",
        "Ya están cargados los bloqueos, retrabajos, reportes, alertas y métricas de recuperación.",
    )

    st.success(
        "Versión enterprise cargada: si antes veías solo solicitud/aprobación/ejecución, ahora también verás Bloqueos, Retrabajo, Reportes y Alertas."
    )

    columns = st.columns(5)
    columns[0].metric("Solicitudes", str(len(requests)))
    columns[1].metric("Pendientes", str(counts.get("Pendiente", 0)))
    columns[2].metric("Retrabajos", str(len(reworks)))
    columns[3].metric("Recuperado", format_money(recovered))
    columns[4].metric("Perdido", format_money(lost))

    st.markdown("### Mejoras visibles de esta versión")
    cards = st.columns(4)
    with cards[0]:
        render_info_card(
            "Bloqueos",
            "Detecta ventas, lotes comprometidos y cierres que impiden reversar sin autorización.",
            "SEGURIDAD",
        )
    with cards[1]:
        render_info_card(
            "Retrabajo",
            "Convierte reversos ejecutados en órdenes de retrabajo vinculadas a producción.",
            "OPERACIÓN",
        )
    with cards[2]:
        render_info_card(
            "Reportes",
            "Exporta CSV y resume reversos por producto, responsable y motivo.",
            "ANÁLISIS",
        )
    with cards[3]:
        render_info_card(
            "Alertas",
            "Detecta productos, responsables o motivos con reversos repetidos.",
            "RIESGO",
        )

    st.caption(
        f"Datos disponibles para control: {len(batches)} lote(s), {len(sales)} venta(s) y {len(reworks)} orden(es) de retrabajo."
    )
    st.divider()
    render_production_reversals_enterprise()


app_shell.FUNCTIONAL_MODULES["Reversos de producción"] = render_production_reversals_visible
app_shell.NAVIGATION_GROUPS["Productos e inventario"] = (
    "Catálogo y producción",
    "Mantenimiento del catálogo",
    "Reversos de producción",
    "Inventario",
    "Movimientos de inventario",
    "Alertas de inventario",
    "Costeo",
    "Ajustar precios",
    "Exportar precios",
)
