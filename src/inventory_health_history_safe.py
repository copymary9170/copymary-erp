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
from src.auth import ADMIN_ROLE_NAME, current_user
from src.erp_database import connect, record_audit_event
from src.inventory_health_summary_safe import _completion, _health_score, _status
from src.inventory_priority_summary_safe import _findings

_TABLE = "inventory_health_snapshots"
_SOURCE_VERSION = "inventory-health-v1"
_PERMISSION_MODULE = "Inventario"
_PERMISSION_ACTION = "health_snapshot_create"


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


def _can_create_snapshot() -> bool:
    user = current_user()
    if user is None:
        return False
    if user.role_name == ADMIN_ROLE_NAME:
        return True
    try:
        with connect() as conn:
            row = conn.execute(
                """
                SELECT allowed FROM app_permissions
                WHERE role_id = ? AND module_name = ? AND action_name = ?
                LIMIT 1
                """,
                (user.role_id, _PERMISSION_MODULE, _PERMISSION_ACTION),
            ).fetchone()
    except Exception:
        return False
    return bool(row and row["allowed"])


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


def _save_measurement(measurement: dict[str, Any], notes: str) -> None:
    user = current_user()
    if user is None or not _can_create_snapshot():
        raise PermissionError("Tu rol no tiene permiso para guardar mediciones de salud de Inventario.")

    recorded_at = datetime.now(timezone.utc).isoformat()
    recorded_by = f"{user.display_name} <{user.email}>"
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
    record_audit_event(
        "inventory",
        _TABLE,
        recorded_at,
        "create_health_snapshot",
        after={**measurement, "recorded_by": recorded_by, "source_version": _SOURCE_VERSION},
        reason=notes.strip() or "Medición manual confirmada",
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

    user = current_user()
    can_create = _can_create_snapshot()
    if user:
        st.caption(f"Usuario autenticado: {user.display_name} · Rol: {user.role_name}")
    if not can_create:
        st.info(
            "Tu rol puede consultar el historial, pero no guardar mediciones. Se requiere el permiso "
            "Inventario / health_snapshot_create o el rol Administrador."
        )

    with st.form("inventory_health_persistent_history_form", clear_on_submit=False):
        notes = st.text_area(
            "Notas",
            max_chars=1000,
            placeholder="Ejemplo: línea base antes de corregir códigos duplicados.",
            disabled=not can_create,
        )
        confirmed = st.checkbox(
            "Confirmo que deseo guardar esta medición en el historial persistente.",
            disabled=not can_create,
        )
        submitted = st.form_submit_button("Guardar medición", type="primary", disabled=not can_create)

    if submitted:
        if not confirmed:
            st.error("Debes confirmar expresamente el guardado.")
        else:
            try:
                _save_measurement(measurement, notes.strip())
            except Exception as exc:
                st.error(f"No fue posible guardar la medición: {exc}")
            else:
                st.success("Medición guardada con usuario autenticado y evento de auditoría.")
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
