"""Restauración segura del respaldo al iniciar CopyMary ERP.

La Configuración General activa pertenece a ``general_settings_process`` y
usa ``margin_method``. Los respaldos antiguos también pueden contener el otro
esquema con ``pricing_method``. Este módulo restaura ambos sin sobrescribir los
clientes, ventas u otros registros de una sesión que ya esté en uso.
"""

from __future__ import annotations

import json

import streamlit as st

from src.erp_database import connect, initialize_database
from src.session_backup import DICT_SECTIONS, LIST_SECTIONS, session_has_data

_STARTUP_RESTORE_MARKER = "_session_snapshot_startup_restore_done"


def _latest_snapshot_data() -> dict | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(
            "SELECT data_json FROM session_snapshots "
            "ORDER BY created_at_utc DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None

    payload = json.loads(row["data_json"])
    if not isinstance(payload, dict) or payload.get("application") != "CopyMary ERP":
        return None
    data = payload.get("data")
    return data if isinstance(data, dict) else None


def _active_general_settings(raw: object):
    """Convierte el diccionario respaldado a la clase realmente activa."""
    if not isinstance(raw, dict):
        return None

    # La interfaz activa usa margin_method. Los snapshots del esquema anterior
    # usaban pricing_method; se acepta como compatibilidad hacia atrás.
    from src.general_settings_process import GeneralSettings

    margin_method = str(raw.get("margin_method") or raw.get("pricing_method") or "Margen sobre venta")
    if margin_method == "Margen sobre costo":
        margin_method = "Recargo sobre costo"

    return GeneralSettings(
        business_name=str(raw.get("business_name") or "Copy Mary").strip(),
        currency=str(raw.get("currency") or "USD").upper(),
        profit_margin=float(raw.get("profit_margin") or 0.0),
        margin_method=margin_method,
        monthly_internet=float(raw.get("monthly_internet") or 0.0),
        monthly_electricity=float(raw.get("monthly_electricity") or 0.0),
        estimated_monthly_units=max(int(raw.get("estimated_monthly_units") or 1), 1),
        bcv_rate=float(raw.get("bcv_rate") or 0.0),
        bcv_eur_rate=float(raw.get("bcv_eur_rate") or 0.0),
        binance_rate=float(raw.get("binance_rate") or 0.0),
        kontigo_in_rate=float(raw.get("kontigo_in_rate") or 0.0),
        kontigo_out_rate=float(raw.get("kontigo_out_rate") or 0.0),
        kontigo_in_fee=float(raw.get("kontigo_in_fee") or 0.0),
        kontigo_out_fee=float(raw.get("kontigo_out_fee") or 0.0),
        iva_rate=float(raw.get("iva_rate", 16.0)),
        igtf_rate=float(raw.get("igtf_rate", 3.0)),
        mobile_payment_fee=float(raw.get("mobile_payment_fee") or 0.0),
        pos_fee=float(raw.get("pos_fee") or 0.0),
        rates_updated_at=str(raw.get("rates_updated_at") or ""),
    )


def _restore_general_settings(data: dict) -> None:
    settings = _active_general_settings(data.get("general_settings"))
    if settings is not None:
        st.session_state["general_settings"] = settings


def _restore_complete_snapshot(data: dict) -> None:
    _restore_general_settings(data)
    for key in LIST_SECTIONS:
        value = data.get(key)
        if isinstance(value, list):
            st.session_state[key] = value
    for key in DICT_SECTIONS:
        value = data.get(key)
        if isinstance(value, dict):
            st.session_state[key] = value


def restore_session_snapshot_on_startup() -> None:
    """Restaura el snapshot una sola vez por sesión de Streamlit.

    Con una sesión vacía recupera todas las secciones. Si ya existen clientes,
    ventas u otros datos, recupera solamente Configuración General.
    """
    if st.session_state.get(_STARTUP_RESTORE_MARKER):
        return

    try:
        data = _latest_snapshot_data()
        if data is not None:
            if session_has_data():
                _restore_general_settings(data)
            else:
                _restore_complete_snapshot(data)
    except Exception:
        # La aplicación debe poder iniciar aunque PostgreSQL esté temporalmente
        # fuera de servicio o exista un snapshot antiguo dañado.
        pass
    finally:
        st.session_state[_STARTUP_RESTORE_MARKER] = True
