"""Guardado manual y lectura del historial de salud de Inventario.

La escritura solo se habilita cuando la migración de la fase 17 ya fue aplicada.
No crea tablas, no ejecuta migraciones y nunca registra mediciones automáticamente.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from src import inventory_enterprise
from src.erp_database import connect
from src.inventory_health_summary_safe import _completion, _health_score, _status
from src.inventory_priority_summary_safe import _findings

_TABLE = "inventory_health_snapshots"
_SOURCE_VERSION = "inventory-health-v1"


def _current_measurement() -> dict[str, Any]:
    rows = list(inventory_enterprise._items())
    findings = _findings(rows)
    counts = Counter(item["Prioridad"] for item in findings)
    completion = _completion(rows)
    score = _health_score(completion, counts, len(rows))
    return {
        "health_score": score,
        "completion_percent": round(completion, 2),
        "total_items": len(rows),
        "critical_findings": counts.get("Crítica", 0),
        "high_findings": counts.get("Alta", 0),
        "medium_findings": counts.get("Media", 0),
        "general_status": _status(score),
    }


def _table_is_ready() -> bool:
    try:
        with connect() as conn:
            conn.execute(f"SELECT recorded_at FROM {_TABLE} LIMIT 1").fetchall()
        return True
    except Exception:
        return False


def _history(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT recorded_at, recorded_by, health_score, completion_percent,
                   total_items, critical_findings, high_findings, medium_findings,
                   general_status, source_version, notes
            FROM {_TABLE}
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _save_measurement(measurement: dict[str, Any], recorded_by: str, notes: str) -> None:
    recorded_at = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute(
            f"""
            INSERT INTO {_TABLE}(
                recorded_at, recorded_by, health_score, completion_percent,
                total_items, critical_findings, high_findings, medium_findings,
                general_status, source_version, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recorded_at,
                recorded_by,
                measurement["health_score"],
                measurement["completion_percent"],
                measurement["total_items"],
                measurement["critical_findings"],
                measurement["high_findings"],
                measurement["medium_findings"],
                measurement["general_status"],
                _SOURCE_VERSION,
                notes or None,
            ),
        )


def _display_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    displayed: list[dict[str, Any]] = []
    for row in rows:
        recorded_at = str(row.get("recorded_at", ""))
        displayed.append({
            "Fecha UTC": recorded_at[:19].replace("T", " "),
            "Registrado por": row.get("recorded_by", ""),
            "Salud": row.get("health_score", 0),
            "Completitud %": row.get("completion_percent", 0),
            "Artículos": row.get("total_items", 0),
            "Críticos": row.get("critical_findings", 0),
            "Altos": row.get("high_findings", 0),
            "Medios": row.get("medium_findings", 0),
            "Estado": row.get("general_status", ""),
            "Notas": row.get("notes") or "",
        })
    return displayed


def render_inventory_health_history() -> None:
    """Permite guardar una medición confirmada y consultar el historial."""
    st.divider()
    st.subheader("Historial persistente de salud")
    st.caption(
        "Las mediciones se guardan únicamente por acción manual. Esta pantalla no crea tablas ni ejecuta migraciones."
    )

    if not _table_is_ready():
        st.warning(
            "La tabla inventory_health_snapshots todavía no está disponible. Aplica y verifica primero la migración de la fase 17."
        )
        return

    measurement = _current_measurement()
    metrics = st.columns(5)
    metrics[0].metric("Índice actual", f"{measurement['health_score']}/100")
    metrics[1].metric("Estado", measurement["general_status"])
    metrics[2].metric("Completitud", f"{measurement['completion_percent']:.1f}%")
    metrics[3].metric("Artículos", measurement["total_items"])
    metrics[4].metric(
        "Hallazgos",
        measurement["critical_findings"] + measurement["high_findings"] + measurement["medium_findings"],
    )

    with st.form("inventory_health_persistent_history_form", clear_on_submit=False):
        recorded_by = st.text_input(
            "Responsable de la medición",
            max_chars=120,
            help="Identifica a la persona que revisó y decidió guardar esta observación.",
        )
        notes = st.text_area(
            "Notas",
            max_chars=1000,
            placeholder="Ejemplo: línea base antes de corregir códigos duplicados.",
        )
        confirmed = st.checkbox(
            "Confirmo que deseo guardar esta medición en el historial persistente.",
        )
        submitted = st.form_submit_button("Guardar medición", type="primary")

    if submitted:
        responsible = recorded_by.strip()
        if not responsible:
            st.error("Indica el responsable antes de guardar.")
        elif not confirmed:
            st.error("Debes confirmar expresamente el guardado.")
        else:
            try:
                _save_measurement(measurement, responsible, notes.strip())
            except Exception as exc:
                st.error(f"No fue posible guardar la medición: {exc}")
            else:
                st.success("Medición guardada con fecha, responsable y métricas auditables.")
                st.rerun()

    try:
        history = _history()
    except Exception as exc:
        st.error(f"La tabla existe, pero no fue posible leer el historial: {exc}")
        return

    st.markdown("#### Mediciones guardadas")
    if not history:
        st.info("La tabla está disponible, pero todavía no contiene mediciones.")
        return

    users = sorted({str(row.get("recorded_by", "")) for row in history if row.get("recorded_by")})
    selected_user = st.selectbox(
        "Filtrar por responsable",
        ["Todos", *users],
        key="inventory_health_history_user_filter",
    )
    filtered = history if selected_user == "Todos" else [
        row for row in history if str(row.get("recorded_by", "")) == selected_user
    ]
    st.dataframe(_display_rows(filtered), use_container_width=True, hide_index=True)
    st.caption(
        "El historial registra el estado observado en cada fecha. No modifica existencias, costos ni políticas de reposición."
    )
