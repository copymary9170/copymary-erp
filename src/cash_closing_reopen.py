"""Reapertura segura del último cierre de caja."""

from datetime import datetime, timezone

import streamlit as st

from src import financial_control
from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active_closings(closings: list[dict]) -> list[dict]:
    return [item for item in closings if not item.get("reopened")]


def _closed_ids(closings: list[dict]) -> set[str]:
    result: set[str] = set()
    for closing in _active_closings(closings):
        for movement_id in closing.get("movement_ids", []):
            result.add(str(movement_id))
    return result


def _opening_by_method(closings: list[dict]) -> dict[str, float]:
    opening = {method: 0.0 for method in financial_control.METHODS}
    for closing in _active_closings(closings):
        counted = closing.get("counted_by_method", {})
        if isinstance(counted, dict):
            for method in financial_control.METHODS:
                if method in counted:
                    opening[method] = float(counted.get(method, 0.0))
    return opening


def activate_closing_reopen_support() -> None:
    """Hace que cierres reabiertos dejen de bloquear movimientos y aperturas."""
    financial_control._closed_ids = _closed_ids
    financial_control._opening_by_method = _opening_by_method


def render_cash_closing_reopen() -> None:
    activate_closing_reopen_support()

    with st.container(border=True):
        render_page_header(
            "Reabrir cierre de caja",
            "Anula el último cierre activo para corregir movimientos y volver a conciliar.",
        )
        st.caption("El cierre permanece en el historial, pero sus movimientos vuelven a quedar pendientes.")

    closings = _rows("cash_closings")
    active = _active_closings(closings)
    reopened = [item for item in closings if item.get("reopened")]

    metrics = st.columns(3)
    metrics[0].metric("Cierres activos", str(len(active)))
    metrics[1].metric("Cierres reabiertos", str(len(reopened)))
    metrics[2].metric(
        "Movimientos liberables",
        str(len(active[-1].get("movement_ids", []))) if active else "0",
    )

    if not active:
        st.info("No hay cierres activos para reabrir.")
    else:
        latest = active[-1]
        with st.container(border=True):
            st.markdown(f"### Último cierre activo · {latest.get('closing_date', '')}")
            st.caption(
                f"ID {latest.get('closing_id', '')} · Responsable: "
                f"{latest.get('responsible') or 'No indicado'}"
            )
            columns = st.columns(4)
            columns[0].metric("Esperado", format_money(float(latest.get("expected_balance", 0.0))))
            columns[1].metric("Contado", format_money(float(latest.get("counted_cash", 0.0))))
            columns[2].metric("Diferencia", format_money(float(latest.get("difference", 0.0))))
            columns[3].metric("Movimientos", str(latest.get("movement_count", 0)))

        with st.form("reopen_latest_cash_closing"):
            reason = st.text_area("Motivo de reapertura", max_chars=300)
            confirmation = st.text_input(
                "Escribe REABRIR para confirmar",
                max_chars=20,
            )
            submitted = st.form_submit_button(
                "Reabrir último cierre",
                type="primary",
                use_container_width=True,
                disabled=confirmation.strip().upper() != "REABRIR",
            )

        if submitted:
            updated: list[dict] = []
            target_id = str(latest.get("closing_id", ""))
            for closing in closings:
                current = dict(closing)
                if str(closing.get("closing_id", "")) == target_id:
                    current["reopened"] = True
                    current["reopened_at_utc"] = _now()
                    current["reopen_reason"] = reason.strip() or "Corrección de cierre"
                    current["reconciliation_status"] = "Reabierto"
                updated.append(current)
            st.session_state["cash_closings"] = updated
            st.success("El último cierre fue reabierto y sus movimientos quedaron disponibles nuevamente.")
            st.rerun()

    st.divider()
    st.subheader("Historial de reaperturas")
    if not reopened:
        st.info("Todavía no hay cierres reabiertos.")
    for closing in reversed(reopened):
        with st.container(border=True):
            st.markdown(f"### Cierre {closing.get('closing_date', '')} · REABIERTO")
            st.caption(
                f"ID {closing.get('closing_id', '')} · {closing.get('reopened_at_utc', '')} · "
                f"{closing.get('reopen_reason') or 'Sin motivo'}"
            )
            st.write(
                f"Movimientos liberados: {len(closing.get('movement_ids', []))} · "
                f"Monto contado original: {format_money(float(closing.get('counted_cash', 0.0)))}"
            )

    render_info_card(
        "Regla de seguridad",
        "Solo puede reabrirse el último cierre activo para conservar la secuencia correcta de aperturas.",
        "CONTROL DE CIERRES",
    )
