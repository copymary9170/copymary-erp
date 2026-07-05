"""Respaldo general temporal de la sesión de CopyMary ERP."""

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone

import streamlit as st

from src.components import render_info_card, render_page_header
from src.general_settings import GeneralSettings


BACKUP_VERSION = 1
SESSION_KEYS = (
    "general_settings",
    "assets_registry",
    "inventory_registry",
    "saved_prices",
)


def _serialize_value(value):
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        serialized = []
        for item in value:
            serialized.append(asdict(item) if is_dataclass(item) else item)
        return serialized
    return value


def _build_backup() -> bytes:
    payload = {
        "backup_version": BACKUP_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "application": "CopyMary ERP",
        "data": {
            key: _serialize_value(st.session_state.get(key))
            for key in SESSION_KEYS
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _validate_general_settings(raw_settings: dict | None) -> GeneralSettings | None:
    if raw_settings is None:
        return None
    required_fields = {
        "business_name",
        "currency",
        "profit_margin",
        "monthly_internet",
        "monthly_electricity",
        "estimated_monthly_units",
        "equipment_name",
        "equipment_cost",
        "equipment_lifetime_units",
    }
    if set(raw_settings.keys()) != required_fields:
        raise ValueError("La configuración general del respaldo no tiene la estructura esperada.")

    currency = str(raw_settings["currency"]).upper()
    if currency not in {"USD", "VES", "EUR"}:
        raise ValueError("La moneda de la configuración debe ser USD, VES o EUR.")

    return GeneralSettings(
        business_name=str(raw_settings["business_name"]).strip(),
        currency=currency,
        profit_margin=float(raw_settings["profit_margin"]),
        monthly_internet=float(raw_settings["monthly_internet"]),
        monthly_electricity=float(raw_settings["monthly_electricity"]),
        estimated_monthly_units=int(raw_settings["estimated_monthly_units"]),
        equipment_name=str(raw_settings["equipment_name"]).strip(),
        equipment_cost=float(raw_settings["equipment_cost"]),
        equipment_lifetime_units=int(raw_settings["equipment_lifetime_units"]),
    )


def _validate_list(name: str, value) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"La sección '{name}' debe contener una lista.")
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"La sección '{name}' contiene un registro inválido.")
    return value


def _parse_backup(file_bytes: bytes) -> dict:
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("El archivo no es un respaldo JSON válido de CopyMary ERP.") from exc

    if not isinstance(payload, dict):
        raise ValueError("El respaldo debe contener un objeto JSON principal.")
    if payload.get("backup_version") != BACKUP_VERSION:
        raise ValueError("La versión del respaldo no es compatible con esta aplicación.")
    if payload.get("application") != "CopyMary ERP":
        raise ValueError("El archivo no fue generado por CopyMary ERP.")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("El respaldo no contiene una sección de datos válida.")

    return {
        "general_settings": _validate_general_settings(data.get("general_settings")),
        "assets_registry": _validate_list("assets_registry", data.get("assets_registry")),
        "inventory_registry": _validate_list("inventory_registry", data.get("inventory_registry")),
        "saved_prices": _validate_list("saved_prices", data.get("saved_prices")),
    }


def _restore_backup(restored_data: dict) -> None:
    settings = restored_data["general_settings"]
    if settings is None:
        st.session_state.pop("general_settings", None)
    else:
        st.session_state.general_settings = settings

    st.session_state.assets_registry = restored_data["assets_registry"]
    st.session_state.inventory_registry = restored_data["inventory_registry"]
    st.session_state.saved_prices = restored_data["saved_prices"]

    for transient_key in (
        "connected_costing_result",
        "connected_costing_asset",
        "connected_costing_material",
        "price_estimate",
    ):
        st.session_state.pop(transient_key, None)


def render_session_backup() -> None:
    """Renderiza el respaldo y restauración general de la sesión."""
    with st.container(border=True):
        render_page_header(
            "Respaldo general",
            "Guarda o recupera en un solo archivo la información temporal principal del ERP.",
        )
        st.caption("Incluye configuración, activos, inventario y lista de precios.")

    st.warning(
        "Este respaldo es manual y provisional. Descárgalo antes de cerrar la sesión para evitar perder datos."
    )

    summary_columns = st.columns(4)
    summary_columns[0].metric(
        "Configuración",
        "Sí" if st.session_state.get("general_settings") is not None else "No",
    )
    summary_columns[1].metric(
        "Activos",
        str(len(st.session_state.get("assets_registry", []))),
    )
    summary_columns[2].metric(
        "Materiales",
        str(len(st.session_state.get("inventory_registry", []))),
    )
    summary_columns[3].metric(
        "Precios",
        str(len(st.session_state.get("saved_prices", []))),
    )

    st.download_button(
        "Descargar respaldo general",
        data=_build_backup(),
        file_name="copymary_respaldo_sesion.json",
        mime="application/json",
        type="primary",
        use_container_width=True,
    )

    st.divider()
    st.subheader("Restaurar respaldo")
    uploaded_file = st.file_uploader(
        "Selecciona un respaldo JSON de CopyMary ERP",
        type=("json",),
        accept_multiple_files=False,
    )
    confirmation = st.checkbox(
        "Entiendo que la restauración reemplazará la configuración, los activos, el inventario y los precios actuales."
    )

    if st.button(
        "Restaurar respaldo general",
        type="primary",
        use_container_width=True,
        disabled=uploaded_file is None or not confirmation,
    ):
        try:
            restored_data = _parse_backup(uploaded_file.getvalue())
        except (TypeError, ValueError) as exc:
            st.error(str(exc))
        else:
            _restore_backup(restored_data)
            st.success("El respaldo general fue restaurado correctamente.")
            st.rerun()

    render_info_card(
        "Contenido del archivo",
        (
            "El JSON contiene únicamente datos operativos temporales de esta versión: configuración general, "
            "activos, materiales y precios guardados."
        ),
        "RESPALDO MANUAL",
    )
