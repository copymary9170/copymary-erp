"""Consulta de tasas usada por Costeo.

La edición vive únicamente en Administración y seguridad → Configuración General.
Esta pantalla conserva el histórico de ``exchange_rates`` porque los trabajos
costeados necesitan trazabilidad y una tasa congelada por fecha.
"""
from __future__ import annotations

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database

TABLE_NAME = "exchange_rates"


def _rows() -> list[dict]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM exchange_rates ORDER BY rate_date DESC, created_at_utc DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def _latest_by_pair(rows: list[dict]) -> dict[tuple[str, str], dict]:
    latest: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["source_currency"], row["target_currency"])
        if key not in latest:
            latest[key] = row
    return latest


def _go_to_master_rates() -> None:
    st.session_state["pending_navigation_area"] = "Administración y seguridad"
    st.session_state["pending_navigation_page"] = "Configuración General"
    st.rerun()


def _render_master_summary() -> None:
    settings = st.session_state.get("general_settings")
    if settings is None:
        st.info("Aún no hay Configuración General cargada en esta sesión.")
        return
    st.markdown("#### Fuente maestra actual")
    cols = st.columns(5)
    cols[0].metric("BCV USD", f"{float(getattr(settings, 'bcv_rate', 0.0) or 0):,.4f} Bs")
    cols[1].metric("BCV EUR", f"{float(getattr(settings, 'bcv_eur_rate', 0.0) or 0):,.4f} Bs")
    cols[2].metric("Binance / paralelo", f"{float(getattr(settings, 'binance_rate', 0.0) or 0):,.4f} Bs")
    cols[3].metric("Kontigo entrada", f"{float(getattr(settings, 'kontigo_in_rate', 0.0) or 0):,.4f} Bs")
    cols[4].metric("Kontigo salida", f"{float(getattr(settings, 'kontigo_out_rate', 0.0) or 0):,.4f} Bs")
    updated = str(getattr(settings, "rates_updated_at", "") or "")
    if updated:
        st.caption(f"Última actualización en Configuración General: {updated[:16].replace('T', ' ')} UTC")
    st.caption(
        "BCV USD y BCV EUR se sincronizan al histórico técnico que usa Costeo. "
        "Binance y Kontigo siguen disponibles para cobros, pagos y análisis, pero no reemplazan la tasa oficial del costeo."
    )


def render_exchange_rates() -> None:
    render_page_header(
        "Tasas usadas en Costeo",
        "Consulta la tasa vigente y el histórico congelado. Las tasas se editan una sola vez desde Configuración General.",
    )
    initialize_database()
    rows = _rows()
    latest = _latest_by_pair(rows)

    st.info(
        "Fuente única de verdad: Administración y seguridad → Configuración General. "
        "Esta pantalla es de consulta para evitar dos formularios que puedan quedar con valores diferentes."
    )
    if st.button("Administrar tasas en Configuración General", type="primary", use_container_width=True):
        _go_to_master_rates()

    _render_master_summary()

    st.divider()
    st.subheader("Tasas oficiales disponibles para Costeo")
    official_latest = {
        pair: row
        for pair, row in latest.items()
        if str(row.get("source_name") or "").startswith("Configuración General · BCV")
    }
    if not official_latest:
        st.warning("Todavía no hay una tasa oficial sincronizada desde Configuración General.")
    else:
        for (source, target), row in official_latest.items():
            st.write(
                f"**1 {source} = {float(row['rate']):,.4f} {target}** · vigente desde {row['rate_date']}"
            )

    st.divider()
    st.subheader("Historial completo")
    st.caption(
        "No se borra el historial anterior. Los registros manuales existentes permanecen visibles para auditoría, "
        "pero las nuevas tasas deben administrarse desde Configuración General."
    )
    if not rows:
        st.info("Sin historial todavía.")
    else:
        st.dataframe(
            [
                {
                    "Fecha": row.get("rate_date"),
                    "Origen": row.get("source_currency"),
                    "Destino": row.get("target_currency"),
                    "Tasa": float(row.get("rate") or 0),
                    "Fuente": row.get("source_name") or "Manual legado",
                    "Notas": row.get("notes") or "",
                }
                for row in rows[:300]
            ],
            use_container_width=True,
            hide_index=True,
        )

    render_info_card(
        "Tasa congelada",
        "Costeo por procesos sigue guardando la tasa exacta usada en cada trabajo. "
        "Cambiar la tasa maestra mañana no altera los costos históricos de trabajos anteriores.",
        "TRAZABILIDAD CONSERVADA",
    )


app_shell.FUNCTIONAL_MODULES["Tasas de cambio"] = render_exchange_rates
