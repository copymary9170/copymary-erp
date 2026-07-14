"""Respaldo general temporal y compatible de CopyMary ERP."""

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone

import streamlit as st

from src.components import render_info_card, render_page_header
from src.general_settings import GeneralSettings

BACKUP_VERSION = 2
LIST_SECTIONS = (
    "customers_registry",
    "quotes_registry",
    "sales_registry",
    "order_plans",
    "payment_records",
    "receivables_registry",
    "cash_movements",
    "cash_closings",
    "expense_records",
    "expense_budgets",
    "recurring_expenses",
    "team_members",
    "team_payments",
    "adjustment_records",
    "suppliers_registry",
    "purchases_registry",
    "supplier_payment_records",
    "payables_registry",
    "products_registry",
    "production_log",
    "assets_registry",
    "inventory_registry",
    "inventory_movements",
    "saved_prices",
)
DICT_SECTIONS = ("business_goals",)
SESSION_KEYS = ("general_settings", *LIST_SECTIONS, *DICT_SECTIONS)
SECTION_LABELS = {
    "general_settings": "Configuración General",
    "customers_registry": "Clientes",
    "quotes_registry": "Cotizaciones",
    "sales_registry": "Ventas y pedidos",
    "order_plans": "Agenda de pedidos",
    "payment_records": "Abonos de clientes",
    "receivables_registry": "Seguimiento de cobro",
    "cash_movements": "Caja",
    "cash_closings": "Cierres de caja",
    "expense_records": "Gastos",
    "expense_budgets": "Presupuestos",
    "recurring_expenses": "Gastos recurrentes",
    "team_members": "Equipo",
    "team_payments": "Pagos al equipo",
    "adjustment_records": "Anulaciones y ajustes",
    "suppliers_registry": "Proveedores",
    "purchases_registry": "Compras",
    "supplier_payment_records": "Pagos a proveedores",
    "payables_registry": "Seguimiento por pagar",
    "products_registry": "Catálogo",
    "production_log": "Producción",
    "assets_registry": "Activos",
    "inventory_registry": "Inventario",
    "inventory_movements": "Movimientos de inventario",
    "saved_prices": "Lista de precios",
    "business_goals": "Metas del negocio",
}


def _serialize(value):
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
        "data": {key: _serialize(st.session_state.get(key)) for key in SESSION_KEYS},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _settings(raw: dict | None) -> GeneralSettings | None:
    if raw is None:
        return None
    # Bug real encontrado: `GeneralSettings` cambió hace poco (equipment_name/
    # equipment_cost/equipment_lifetime_units se reemplazaron por
    # pricing_method + selected_asset_ids, vinculado a Activos reales), pero
    # esta función se quedó validando el esquema VIEJO. Resultado: exportar
    # un respaldo funcionaba, pero restaurarlo fallaba siempre con "La
    # configuración general no tiene la estructura esperada" — la app nunca
    # llegaba a construir un GeneralSettings válido. Además, antes se exigía
    # coincidencia EXACTA de claves (`!=` en vez de subconjunto), lo cual es
    # frágil ante cualquier evolución futura del esquema; ahora sólo se
    # exigen los campos obligatorios y los opcionales (tasas de cambio, IVA,
    # IGTF, comisiones) se completan con su valor por defecto si faltan.
    required = {
        "business_name", "currency", "profit_margin", "pricing_method",
        "monthly_internet", "monthly_electricity", "estimated_monthly_units",
        "selected_asset_ids",
    }
    if not isinstance(raw, dict) or not required.issubset(raw.keys()):
        raise ValueError("La configuración general no tiene la estructura esperada.")
    currency = str(raw["currency"]).upper()
    if currency not in {"USD", "VES", "EUR"}:
        raise ValueError("La moneda debe ser USD, VES o EUR.")
    optional_defaults = {
        "bcv_rate": 0.0, "binance_rate": 0.0, "kontigo_in_rate": 0.0, "kontigo_out_rate": 0.0,
        "iva_rate": 16.0, "igtf_rate": 3.0, "mobile_payment_fee": 0.0, "pos_fee": 0.0,
    }
    return GeneralSettings(
        business_name=str(raw["business_name"]).strip(),
        currency=currency,
        profit_margin=float(raw["profit_margin"]),
        pricing_method=str(raw["pricing_method"]),
        monthly_internet=float(raw["monthly_internet"]),
        monthly_electricity=float(raw["monthly_electricity"]),
        estimated_monthly_units=int(raw["estimated_monthly_units"]),
        selected_asset_ids=tuple(raw["selected_asset_ids"]),
        **{key: float(raw.get(key, default)) for key, default in optional_defaults.items()},
    )


def _parse_backup(file_bytes: bytes) -> dict:
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("El archivo no es un respaldo JSON válido.") from exc
    if not isinstance(payload, dict) or payload.get("application") != "CopyMary ERP":
        raise ValueError("El archivo no fue generado por CopyMary ERP.")
    version = int(payload.get("backup_version", 0))
    if version not in {1, 2}:
        raise ValueError("La versión del respaldo no es compatible.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("El respaldo no contiene datos válidos.")

    restored = {
        "created_at_utc": str(payload.get("created_at_utc", "No disponible")),
        "present_sections": set(data.keys()),
        "general_settings": _settings(data.get("general_settings")),
    }
    for key in LIST_SECTIONS:
        value = data.get(key, [])
        if value is None:
            value = []
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ValueError(f"La sección '{SECTION_LABELS[key]}' contiene datos inválidos.")
        restored[key] = value
    for key in DICT_SECTIONS:
        value = data.get(key, {})
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise ValueError(f"La sección '{SECTION_LABELS[key]}' debe contener un objeto.")
        restored[key] = value
    return restored


def _restore(data: dict, selected: list[str]) -> None:
    present = data["present_sections"]
    for key in selected:
        if key not in present:
            continue
        if key == "general_settings":
            if data[key] is None:
                st.session_state.pop(key, None)
            else:
                st.session_state[key] = data[key]
        else:
            st.session_state[key] = data[key]
    for key in ("connected_costing_result", "connected_costing_asset", "connected_costing_material", "price_estimate"):
        st.session_state.pop(key, None)


def _count(value) -> str:
    if value is None:
        return "Vacío"
    if isinstance(value, dict):
        return "Disponible" if value else "Vacío"
    if isinstance(value, list):
        return str(len(value))
    return "Disponible"


def _metrics(values: dict[str, str]) -> None:
    items = list(values.items())
    for start in range(0, len(items), 4):
        chunk = items[start:start + 4]
        columns = st.columns(len(chunk))
        for column, (label, value) in zip(columns, chunk, strict=True):
            column.metric(label, value)


def render_session_backup() -> None:
    with st.container(border=True):
        render_page_header("Respaldo general", "Guarda o recupera toda la información temporal principal del ERP.")
        st.caption("Incluye metas, equipo, pagos internos, ajustes, ventas, compras, caja, producción e inventario.")

    st.warning("Descarga este respaldo antes de cerrar la sesión para evitar perder datos.")
    _metrics({SECTION_LABELS[key]: _count(st.session_state.get(key)) for key in SESSION_KEYS})

    st.download_button(
        "Descargar respaldo general",
        data=_build_backup(),
        file_name="copymary_respaldo_sesion_v2.json",
        mime="application/json",
        type="primary",
        use_container_width=True,
    )

    st.divider()
    uploaded = st.file_uploader("Selecciona un respaldo JSON de CopyMary ERP", type=("json",))
    if uploaded is not None:
        try:
            restored = _parse_backup(uploaded.getvalue())
        except (TypeError, ValueError) as exc:
            st.error(str(exc))
        else:
            present = restored["present_sections"]
            st.success("El archivo es válido y compatible.")
            st.caption(f"Fecha UTC: {restored['created_at_utc']}")
            available = [key for key in SESSION_KEYS if key in present]
            _metrics({SECTION_LABELS[key]: _count(restored[key]) for key in available})
            selected = st.multiselect(
                "Secciones que deseas restaurar",
                options=available,
                default=available,
                format_func=lambda key: SECTION_LABELS[key],
            )
            confirmation = st.checkbox("Entiendo que las secciones seleccionadas reemplazarán sus datos actuales.")
            if st.button("Restaurar secciones seleccionadas", type="primary", use_container_width=True, disabled=not selected or not confirmation):
                _restore(restored, selected)
                st.success(f"Se restauraron {len(selected)} sección(es).")
                st.rerun()

    render_info_card("Compatibilidad", "Los respaldos antiguos pueden restaurarse sin borrar las secciones nuevas que no existían en el archivo.", "RESPALDO V2")
