"""Plan descargable de revisión para hallazgos de Inventario.

La vista reutiliza el diagnóstico existente y prepara una cola de trabajo de
solo lectura. Descargar el archivo no modifica registros del ERP.
"""
from __future__ import annotations

import csv
import io
from collections import Counter

import streamlit as st

from src import inventory_enterprise
from src.inventory_action_permissions import can_inventory_action
from src.inventory_priority_summary_safe import _findings


def _module_for_action(action: str) -> str:
    text = action.casefold()
    if "catálogo" in text:
        return "Catálogo"
    if "compras" in text and "recepción" in text:
        return "Compras / Recepción"
    if "movimientos" in text or "conteo" in text or "reservas" in text:
        return "Inventario"
    if "reposición" in text:
        return "Reposición"
    return "Inventario"


def _rows_for_export() -> list[dict[str, str]]:
    findings = _findings(inventory_enterprise._items())
    priority_order = {"Crítica": 0, "Alta": 1, "Media": 2}
    rows: list[dict[str, str]] = []
    for item in findings:
        action = item["Acción recomendada"]
        rows.append({
            "Prioridad": item["Prioridad"],
            "Artículo": item["Artículo"],
            "Hallazgo": item["Hallazgo"],
            "Módulo responsable": _module_for_action(action),
            "Acción recomendada": action,
            "Estado sugerido": "Pendiente de revisión",
        })
    return sorted(rows, key=lambda row: (priority_order.get(row["Prioridad"], 99), row["Artículo"]))


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    if not rows:
        return b""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def render_inventory_review_plan() -> None:
    """Muestra y permite descargar un plan de revisión sin alterar datos."""
    rows = _rows_for_export()
    can_download = can_inventory_action("report_download")

    st.divider()
    st.subheader("Plan de revisión de inventario")
    st.caption(
        "Cola de trabajo generada a partir de los hallazgos actuales. Es de solo lectura y no marca tareas como resueltas."
    )

    if not rows:
        st.success("No hay hallazgos para incorporar al plan de revisión.")
        return

    module_counts = Counter(row["Módulo responsable"] for row in rows)
    columns = st.columns(4)
    columns[0].metric("Acciones pendientes", len(rows))
    columns[1].metric("Catálogo", module_counts.get("Catálogo", 0))
    columns[2].metric("Compras / Recepción", module_counts.get("Compras / Recepción", 0))
    columns[3].metric("Inventario", module_counts.get("Inventario", 0))

    selected_module = st.selectbox(
        "Filtrar por módulo responsable",
        ["Todos", *sorted(module_counts)],
        key="inventory_review_plan_module",
    )
    filtered = rows if selected_module == "Todos" else [
        row for row in rows if row["Módulo responsable"] == selected_module
    ]
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    if not can_download:
        st.warning("Tu rol puede consultar el plan, pero no tiene permiso para descargar informes de Inventario.")
    st.download_button(
        "Descargar plan en CSV",
        data=_csv_bytes(rows),
        file_name="plan_revision_inventario.csv",
        mime="text/csv",
        key="inventory_review_plan_download",
        disabled=not can_download,
    )
    st.info(
        "El archivo sirve para asignar responsables y documentar el seguimiento fuera de esta pantalla. "
        "Las correcciones deben realizarse en el módulo indicado y conservar su trazabilidad normal."
    )
