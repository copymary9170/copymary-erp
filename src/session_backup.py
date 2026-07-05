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
    required = {
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
    if set(raw.keys()) != required:
        raise ValueError("La configuración general no tiene la estructura esperada.")
    currency = str(raw["currency"]).upper()
    if currency not in {"USD", "VES", "EUR"}:
        raise ValueError("La moneda debe ser USD, VES o EUR.")
    return GeneralSettings(
        business_name=str(raw["business_name"]).strip(),
        currency=currency,
        profit_margin=float(raw["profit_margin"]),
        monthly_internet=float(raw["monthly_internet"]),
        monthly_electricity=float(raw["monthly_electricity"]),
        estimated_monthly_units=int(raw["estimated_monthly_units"]),
        equipment_name=str(raw["equipment_name"]).strip(),
        equipment_cost=float(raw["equipment_cost"]),
        equipment_lifetime_units=int(raw["equipment_lifetime_units"]),
    )


def _list_value(name: str, value) -> list:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"La sección '{name}' contiene datos inválidos.")
    return value


def _parse_backup(file_bytes: bytes) -> dict:
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("El archivo no es un respaldo JSON válido.") from exc
    if not isinstance(payload, dict) or payload.get("application") != "CopyMary ERP":
        raise ValueError("El archivo no fue generado por CopyMary ERP.")
    if payload.get("backup_version") != BACKUP_VERSION:
        raise ValueError("La versión del respaldo no es compatible.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("El respaldo no contiene datos válidos.")
    restored = {
        "created_at_utc": str(payload.get("created_at_utc", "No disponible")),
        "general_settings": _settings(data.get("general_settings")),
    }
    for key in SESSION_KEYS:
        if key != "general_settings":
            restored[key] = _list_value(key, data.get(key))
    return restored


def _restore(data: dict, selected: list[str]) -> None:
    if "general_settings" in selected:
        settings = data["general_settings"]
        if settings is None:
            st.session_state.pop("general_settings", None)
        else:
            st.session_state["general_settings"] = settings
    for key in selected:
        if key != "general_settings":
            st.session_state[key] = data[key]
    for key in ("connected_costing_result", "connected_costing_asset", "connected_costing_material", "price_estimate"):
        st.session_state.pop(key, None)


def _section_value(data: dict, key: str) -> str:
    if key == "general_settings":
        return "Disponible" if data.get(key) is not None else "Vacía"
    return str(len(data.get(key, [])))


def _metrics(values: dict[str, str]) -> None:
    items = list(values.items())
    for start in range(0, len(items), 4):
        chunk = items[start : start + 4]
        columns = st.columns(len(chunk))
        for column, (label, value) in zip(columns, chunk, strict=True):
            column.metric(label, value)


def render_session_backup() -> None:
    with st.container(border=True):
        render_page_header("Respaldo general", "Guarda o recupera la información temporal principal del ERP.")
        st.caption("Incluye ventas, agenda, cobranza, caja, cierres, gastos, presupuestos, pagos, producción e inventario.")

    st.warning("Descarga este respaldo antes de cerrar la sesión para evitar perder datos.")
    current = {}
    for key in SESSION_KEYS:
        current[SECTION_LABELS[key]] = "Sí" if key == "general_settings" and st.session_state.get(key) is not None else "No" if key == "general_settings" else str(len(st.session_state.get(key, [])))
    _metrics(current)

    st.download_button(
        "Descargar respaldo general",
        data=_build_backup(),
        file_name="copymary_respaldo_sesion.json",
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
            st.success("El archivo es válido.")
            st.caption(f"Fecha del respaldo en UTC: {restored['created_at_utc']}")
            _metrics({SECTION_LABELS[key]: _section_value(restored, key) for key in SESSION_KEYS})
            selected = st.multiselect(
                "Secciones que deseas restaurar",
                options=list(SESSION_KEYS),
                default=list(SESSION_KEYS),
                format_func=lambda key: SECTION_LABELS[key],
            )
            confirmation = st.checkbox("Entiendo que las secciones seleccionadas reemplazarán sus datos actuales.")
            if st.button("Restaurar secciones seleccionadas", type="primary", use_container_width=True, disabled=not selected or not confirmation):
                _restore(restored, selected)
                st.success(f"Se restauraron {len(selected)} sección(es).")
                st.rerun()

    render_info_card("Restauración selectiva", "Puedes recuperar por separado cualquiera de las secciones principales del ERP.", "CONTROL DE RESTAURACIÓN")
