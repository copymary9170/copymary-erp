"""Comparación temporal segura de indicadores de Inventario.

Guarda puntos únicamente en la sesión activa de Streamlit. No escribe en la
base de datos ni presenta una serie histórica cuando no existen observaciones.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

import streamlit as st

from src import inventory_enterprise
from src.inventory_health_summary_safe import _completion, _health_score, _status
from src.inventory_priority_summary_safe import _findings


_SESSION_KEY = "inventory_health_observations"


def _current_observation() -> dict[str, object]:
    rows = list(inventory_enterprise._items())
    findings = _findings(rows)
    counts = Counter(item["Prioridad"] for item in findings)
    completion = _completion(rows)
    score = _health_score(completion, counts, len(rows))
    return {
        "Momento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Índice de salud": score,
        "Datos completos (%)": round(completion, 1),
        "Artículos": len(rows),
        "Críticos": counts.get("Crítica", 0),
        "Altos": counts.get("Alta", 0),
        "Medios": counts.get("Media", 0),
        "Estado": _status(score),
    }


def render_inventory_health_trend() -> None:
    """Permite comparar observaciones de la sesión sin alterar registros."""
    observations = st.session_state.setdefault(_SESSION_KEY, [])
    current = _current_observation()

    st.divider()
    st.subheader("Comparación temporal de salud")
    st.caption(
        "Las observaciones se conservan solo durante esta sesión. No constituyen un historial contable ni se guardan en la base de datos."
    )

    if st.button("Guardar observación actual", key="inventory_health_save_observation"):
        observations.append(current)
        st.success("Observación guardada en esta sesión.")

    columns = st.columns(4)
    columns[0].metric("Observaciones", len(observations))
    columns[1].metric("Índice actual", f"{current['Índice de salud']}/100")
    columns[2].metric("Completitud actual", f"{current['Datos completos (%)']}%")
    columns[3].metric("Estado actual", str(current["Estado"]))

    if not observations:
        st.info("Guarda una primera observación para establecer una línea base de esta sesión.")
        return

    st.dataframe(observations, use_container_width=True, hide_index=True)

    if len(observations) >= 2:
        chart_rows = [
            {
                "Momento": item["Momento"],
                "Índice de salud": item["Índice de salud"],
                "Datos completos (%)": item["Datos completos (%)"],
            }
            for item in observations
        ]
        st.line_chart(chart_rows, x="Momento", y=["Índice de salud", "Datos completos (%)"])

        first = observations[0]
        latest = observations[-1]
        delta_score = int(latest["Índice de salud"]) - int(first["Índice de salud"])
        delta_completion = float(latest["Datos completos (%)"]) - float(first["Datos completos (%)"])
        st.caption(
            f"Cambio desde la primera observación: índice {delta_score:+d} puntos; completitud {delta_completion:+.1f} puntos porcentuales."
        )
    else:
        st.info("Guarda una segunda observación después de revisar datos para visualizar la tendencia.")

    if st.button("Limpiar observaciones de la sesión", key="inventory_health_clear_observations"):
        observations.clear()
        st.rerun()
