"""Auditoría unificada y de solo lectura para Inventario."""
from __future__ import annotations

import csv
import io
from datetime import date

import streamlit as st

from src.erp_database import connect
from src.inventory_action_permissions import can_inventory_action
from src.session_utils import read_list


def _event(timestamp="", event_type="", article="", user="", reference="", detail="", source="") -> dict[str, str]:
    return {
        "Fecha UTC": str(timestamp or ""),
        "Tipo": str(event_type or ""),
        "Artículo": str(article or ""),
        "Usuario / responsable": str(user or ""),
        "Referencia": str(reference or ""),
        "Detalle": str(detail or ""),
        "Fuente": source,
    }


def _session_events() -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for row in read_list("inventory_movements"):
        events.append(_event(
            row.get("created_at_utc"), row.get("movement_type") or "Movimiento",
            row.get("item_name"), row.get("responsible") or row.get("created_by"),
            row.get("purchase_id") or row.get("invoice_number") or row.get("receipt_id"),
            f"Cantidad {row.get('quantity', 0)} · anterior {row.get('previous_quantity', 0)} · "
            f"resultante {row.get('resulting_quantity', 0)} · {row.get('reason', '')}",
            "Movimientos",
        ))

    for row in read_list("inventory_reservations"):
        article = row.get("item_name") or row.get("item_id")
        reference = row.get("reference") or row.get("reservation_id")
        events.append(_event(
            row.get("created_at_utc"), "Reserva creada", article, row.get("responsible"), reference,
            f"Cantidad {row.get('quantity', 0)} · origen {row.get('source', '')}", "Reservas",
        ))
        if row.get("released_at_utc"):
            events.append(_event(row.get("released_at_utc"), "Reserva liberada", article,
                                 row.get("closed_by_or_reason"), reference,
                                 f"Cantidad {row.get('quantity', 0)}", "Reservas"))
        if row.get("consumed_at_utc"):
            events.append(_event(row.get("consumed_at_utc"), "Reserva consumida", article,
                                 row.get("closed_by_or_reason"), reference,
                                 f"Cantidad {row.get('quantity', 0)}", "Reservas"))

    for row in read_list("inventory_count_sessions"):
        events.append(_event(
            row.get("created_at_utc"), "Conteo físico aplicado",
            row.get("item_name") or row.get("item_id"), row.get("reference"), row.get("count_id"),
            f"Sistema {row.get('system_quantity', 0)} · contado {row.get('counted_quantity', 0)} · "
            f"diferencia {row.get('difference', 0)}", "Conteos",
        ))

    for row in read_list("inventory_metadata_audit"):
        changes = row.get("changes") or {}
        detail = "; ".join(
            f"{field}: {values.get('before', '') or '—'} → {values.get('after', '') or '—'}"
            for field, values in changes.items()
        )
        events.append(_event(
            row.get("created_at_utc"), "Metadatos logísticos actualizados",
            row.get("item_name") or row.get("item_id"), row.get("reason"), row.get("audit_id"),
            detail, "Metadatos",
        ))
    return events


def _health_events() -> list[dict[str, str]]:
    try:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT recorded_at, recorded_by, health_score, completion_percent,
                       total_items, critical_findings, high_findings, medium_findings,
                       general_status, source_version, notes
                FROM inventory_health_snapshots
                ORDER BY recorded_at DESC
                LIMIT 500
                """
            ).fetchall()
    except Exception:
        return []
    return [
        _event(
            row["recorded_at"], "Medición de salud guardada", "", row["recorded_by"],
            row["source_version"],
            f"Salud {row['health_score']}/100 · completitud {row['completion_percent']}% · "
            f"artículos {row['total_items']} · críticos {row['critical_findings']} · "
            f"altos {row['high_findings']} · medios {row['medium_findings']} · "
            f"estado {row['general_status']} · {row['notes'] or ''}",
            "Salud persistente",
        )
        for row in rows
    ]


def _all_events() -> list[dict[str, str]]:
    return sorted([*_session_events(), *_health_events()], key=lambda row: row["Fecha UTC"], reverse=True)


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    if not rows:
        return b""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def render_inventory_unified_audit() -> None:
    """Consolida trazas existentes con filtros, sin realizar escrituras."""
    st.divider()
    st.subheader("Auditoría unificada de Inventario")
    st.caption("Vista de solo lectura. No permite editar ni eliminar eventos históricos.")

    if not can_inventory_action("audit_view"):
        st.warning("Tu rol no tiene permiso para consultar la auditoría unificada de Inventario.")
        return

    events = _all_events()
    if not events:
        st.info("No hay eventos disponibles en las fuentes de auditoría actuales.")
        return

    types = sorted({row["Tipo"] for row in events})
    sources = sorted({row["Fuente"] for row in events})
    a, b, c = st.columns(3)
    selected_type = a.selectbox("Tipo de operación", ["Todos", *types], key="inventory_audit_type")
    selected_source = b.selectbox("Fuente", ["Todas", *sources], key="inventory_audit_source")
    query = c.text_input("Buscar artículo, usuario o referencia", key="inventory_audit_query")
    d, e = st.columns(2)
    start_date = d.date_input("Desde", value=None, key="inventory_audit_from")
    end_date = e.date_input("Hasta", value=None, key="inventory_audit_to")

    filtered: list[dict[str, str]] = []
    for row in events:
        if selected_type != "Todos" and row["Tipo"] != selected_type:
            continue
        if selected_source != "Todas" and row["Fuente"] != selected_source:
            continue
        haystack = " ".join((row["Artículo"], row["Usuario / responsable"], row["Referencia"], row["Detalle"])).casefold()
        if query and query.casefold() not in haystack:
            continue
        try:
            event_date = date.fromisoformat(row["Fecha UTC"][:10])
        except ValueError:
            event_date = None
        if start_date and event_date and event_date < start_date:
            continue
        if end_date and event_date and event_date > end_date:
            continue
        filtered.append(row)

    metrics = st.columns(4)
    metrics[0].metric("Eventos encontrados", len(filtered))
    metrics[1].metric("Fuentes", len({row["Fuente"] for row in filtered}))
    metrics[2].metric("Tipos", len({row["Tipo"] for row in filtered}))
    metrics[3].metric("Artículos identificados", len({row["Artículo"] for row in filtered if row["Artículo"]}))
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    can_download = can_inventory_action("report_download")
    if not can_download:
        st.info("La consulta está permitida, pero tu rol no puede descargar informes de Inventario.")
    st.download_button(
        "Descargar auditoría filtrada en CSV",
        data=_csv_bytes(filtered),
        file_name="auditoria_inventario.csv",
        mime="text/csv",
        key="inventory_unified_audit_download",
        disabled=not can_download or not filtered,
    )
