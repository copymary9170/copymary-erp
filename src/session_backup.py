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
    "customers_registry",
    "sales_registry",
    "cash_movements",
    "assets_registry",
    "inventory_registry",
    "inventory_movements",
    "saved_prices",
)
SECTION_LABELS = {
    "general_settings": "Configuración General",
    "customers_registry": "Clientes",
    "sales_registry": "Ventas y pedidos",
    "cash_movements": "Caja",
    "assets_registry": "Activos",
    "inventory_registry": "Inventario",
    "inventory_movements": "Movimientos de inventario",
    "saved_prices": "Lista de precios",
}


def _serialize_value(value):
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [asdict(item) if is_dataclass(item) else item for item in value]
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

    restored = {
        "created_at_utc": str(payload.get("created_at_utc", "No disponible")),
        "general_settings": _validate_general_settings(data.get("general_settings")),
    }
    for key in SESSION_KEYS:
        if key == "general_settings":
            continue
        restored[key] = _validate_list(key, data.get(key))
    return restored


def _restore_selected_sections(restored_data: dict, selected_sections: list[str]) -> None:
    if "general_settings" in selected_sections:
        settings = restored_data["general_settings"]
        if settings is None:
            st.session_state.pop("general_settings", None)
        else:
            st.session_state.general_settings = settings

    for section in selected_sections:
        if section == "general_settings":
            continue
        st.session_state[section] = restored_data[section]

    for transient_key in (
        "connected_costing_result",
        "connected_costing_asset",
        "connected_costing_material",
        "price_estimate",
    ):
        st.session_state.pop(transient_key, None)


def _section_count(restored_data: dict, section: str) -> str:
    if section == "general_settings":
        return "Disponible" if restored_data[section] is not None else "Vacía"
    return str(len(restored_data[section]))


def render_session_backup() -> None:
    """Renderiza el respaldo y restauración selectiva de la sesión."""
    with st.container(border=True):
        render_page_header(
            "Respaldo general",
            "Guarda o recupera en un solo archivo la información temporal principal del ERP.",
        )
        st.caption(
            "Incluye configuración, clientes, ventas, caja, activos, inventario, movimientos y precios."
        )

    st.warning(
        "Este respaldo es manual y provisional. Descárgalo antes de cerrar la sesión para evitar perder datos."
    )

    summary_columns = st.columns(4)
    summary_columns[0].metric(
        "Configuración",
        "Sí" if st.session_state.get("general_settings") is not None else "No",
    )
    summary_columns[1].metric("Clientes", str(len(st.session_state.get("customers_registry", []))))
    summary_columns[2].metric("Ventas", str(len(st.session_state.get("sales_registry", []))))
    summary_columns[3].metric("Caja", str(len(st.session_state.get("cash_movements", []))))

    summary_columns_2 = st.columns(4)
    summary_columns_2[0].metric("Activos", str(len(st.session_state.get("assets_registry", []))))
    summary_columns_2[1].metric("Materiales", str(len(st.session_state.get("inventory_registry", []))))
    summary_columns_2[2].metric(
        "Movimientos",
        str(len(st.session_state.get("inventory_movements", []))),
    )
    summary_columns_2[3].metric("Precios", str(len(st.session_state.get("saved_prices", []))))

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

    restored_data = None
    if uploaded_file is not None:
        try:
            restored_data = _parse_backup(uploaded_file.getvalue())
        except (TypeError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.success("El archivo es válido. Revisa el contenido antes de restaurar.")
            st.caption(f"Fecha del respaldo en UTC: {restored_data['created_at_utc']}")

            preview_columns = st.columns(4)
            preview_columns_2 = st.columns(4)
            for index, section in enumerate(SESSION_KEYS):
                columns = preview_columns if index < 4 else preview_columns_2
                columns[index % 4].metric(SECTION_LABELS[section], _section_count(restored_data, section))

            selected_sections = st.multiselect(
                "Secciones que deseas restaurar",
                options=list(SESSION_KEYS),
                default=list(SESSION_KEYS),
                format_func=lambda section: SECTION_LABELS[section],
            )

            if selected_sections:
                affected_names = ", ".join(SECTION_LABELS[section] for section in selected_sections)
                st.info(f"Se reemplazarán únicamente estas secciones: {affected_names}.")
            else:
                st.warning("Selecciona por lo menos una sección para continuar.")

            confirmation = st.checkbox(
                "Entiendo que las secciones seleccionadas reemplazarán sus datos actuales."
            )

            if st.button(
                "Restaurar secciones seleccionadas",
                type="primary",
                use_container_width=True,
                disabled=not selected_sections or not confirmation,
            ):
                _restore_selected_sections(restored_data, selected_sections)
                st.success(
                    f"Se restauraron correctamente {len(selected_sections)} sección(es)."
                )
                st.rerun()

    render_info_card(
        "Restauración selectiva",
        (
            "Puedes recuperar por separado Configuración, Clientes, Ventas, Caja, Activos, Inventario, "
            "Movimientos o Lista de precios."
        ),
        "CONTROL DE RESTAURACIÓN",
    )
