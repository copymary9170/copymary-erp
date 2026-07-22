"""Respaldo general temporal y compatible de CopyMary ERP."""

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.erp_database import connect, get_database_status, initialize_database

MAX_CLOUD_SNAPSHOTS = 10
BACKUP_VERSION = 2
LIST_SECTIONS = (
    "customers_registry", "quotes_registry", "sales_registry", "order_plans",
    "payment_records", "receivables_registry", "cash_movements", "cash_closings",
    "expense_records", "expense_budgets", "recurring_expenses", "team_members",
    "team_payments", "adjustment_records", "suppliers_registry", "purchases_registry",
    "supplier_payment_records", "payables_registry", "products_registry", "production_log",
    "assets_registry", "inventory_registry", "inventory_movements", "saved_prices",
)
DICT_SECTIONS = ("business_goals",)
SESSION_KEYS = ("general_settings", *LIST_SECTIONS, *DICT_SECTIONS)
SECTION_LABELS = {
    "general_settings": "Configuración General", "customers_registry": "Clientes",
    "quotes_registry": "Cotizaciones", "sales_registry": "Ventas y pedidos",
    "order_plans": "Agenda de pedidos", "payment_records": "Abonos de clientes",
    "receivables_registry": "Seguimiento de cobro", "cash_movements": "Caja",
    "cash_closings": "Cierres de caja", "expense_records": "Gastos",
    "expense_budgets": "Presupuestos", "recurring_expenses": "Gastos recurrentes",
    "team_members": "Equipo", "team_payments": "Pagos al equipo",
    "adjustment_records": "Anulaciones y ajustes", "suppliers_registry": "Proveedores",
    "purchases_registry": "Compras", "supplier_payment_records": "Pagos a proveedores",
    "payables_registry": "Seguimiento por pagar", "products_registry": "Catálogo",
    "production_log": "Producción", "assets_registry": "Activos",
    "inventory_registry": "Inventario", "inventory_movements": "Movimientos de inventario",
    "saved_prices": "Lista de precios", "business_goals": "Metas del negocio",
}


def _serialize(value):
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [asdict(item) if is_dataclass(item) else item for item in value]
    return value


def _backup_payload() -> dict:
    return {
        "backup_version": BACKUP_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "application": "CopyMary ERP",
        "data": {key: _serialize(st.session_state.get(key)) for key in SESSION_KEYS},
    }


def _build_backup() -> bytes:
    return json.dumps(_backup_payload(), ensure_ascii=False, indent=2).encode("utf-8")


def save_snapshot_to_database() -> dict:
    payload = _backup_payload()
    data_json = json.dumps(payload, ensure_ascii=False)
    sections_included = sum(1 for value in payload["data"].values() if value)
    snapshot_id = f"SNAP-{uuid4().hex[:10].upper()}"
    created_at = payload["created_at_utc"]

    initialize_database()
    with connect() as conn:
        conn.execute(
            "INSERT INTO session_snapshots(snapshot_id, data_json, sections_included, size_bytes, created_at_utc) VALUES (?, ?, ?, ?, ?)",
            (snapshot_id, data_json, sections_included, len(data_json.encode("utf-8")), created_at),
        )
        old_ids = [
            row["snapshot_id"]
            for row in conn.execute(
                "SELECT snapshot_id FROM session_snapshots ORDER BY created_at_utc DESC"
            ).fetchall()
        ][MAX_CLOUD_SNAPSHOTS:]
        for old_id in old_ids:
            conn.execute("DELETE FROM session_snapshots WHERE snapshot_id = ?", (old_id,))

    return {
        "snapshot_id": snapshot_id,
        "sections_included": sections_included,
        "size_bytes": len(data_json.encode("utf-8")),
        "created_at_utc": created_at,
    }


def latest_snapshot_info() -> dict | None:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(
            "SELECT snapshot_id, sections_included, size_bytes, created_at_utc FROM session_snapshots ORDER BY created_at_utc DESC LIMIT 1"
        ).fetchall()
    return dict(rows[0]) if rows else None


def _latest_snapshot_row() -> dict | None:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM session_snapshots ORDER BY created_at_utc DESC LIMIT 1"
        ).fetchall()
    return dict(rows[0]) if rows else None


def restore_latest_snapshot_from_database() -> dict | None:
    row = _latest_snapshot_row()
    if row is None:
        return None
    restored = _parse_backup(row["data_json"].encode("utf-8"))
    _restore(restored, [key for key in SESSION_KEYS if key in restored["present_sections"]])
    return row


def session_has_data() -> bool:
    return any(st.session_state.get(key) for key in SESSION_KEYS)


def restore_latest_snapshot_on_startup() -> None:
    """Restaura sin sobrescribir trabajo ya cargado.

    En una sesión totalmente vacía restaura el respaldo completo. Si otras
    secciones ya fueron inicializadas pero falta Configuración General, recupera
    únicamente ``general_settings``. Así las tasas sobreviven al reload sin
    reemplazar inventario, ventas, clientes ni otros datos activos.
    """
    settings_missing = not st.session_state.get("general_settings")
    if session_has_data() and not settings_missing:
        return

    try:
        row = _latest_snapshot_row()
        if row is None:
            return
        restored = _parse_backup(row["data_json"].encode("utf-8"))
        if session_has_data():
            if (
                settings_missing
                and "general_settings" in restored["present_sections"]
                and restored.get("general_settings") is not None
            ):
                _restore(restored, ["general_settings"])
        else:
            selected = [key for key in SESSION_KEYS if key in restored["present_sections"]]
            _restore(restored, selected)
    except Exception:
        pass


def _settings(raw: dict | None):
    from src.general_settings import GeneralSettings

    if raw is None:
        return None
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
        "bcv_rate": 0.0, "bcv_eur_rate": 0.0, "binance_rate": 0.0,
        "kontigo_in_rate": 0.0, "kontigo_out_rate": 0.0,
        "kontigo_in_fee": 0.0, "kontigo_out_fee": 0.0,
        "iva_rate": 16.0, "igtf_rate": 3.0, "mobile_payment_fee": 0.0,
        "pos_fee": 0.0,
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
        rates_updated_at=str(raw.get("rates_updated_at", "") or ""),
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
    for key in (
        "connected_costing_result", "connected_costing_asset",
        "connected_costing_material", "price_estimate",
    ):
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
        render_page_header(
            "Respaldo general",
            "Guarda o recupera toda la información temporal principal del ERP.",
        )
        st.caption("Incluye metas, equipo, pagos internos, ajustes, ventas, compras, caja, producción e inventario.")

    db_status = get_database_status()
    is_durable = db_status.engine == "postgresql"
    st.markdown("### Respaldo automático en la nube")
    if is_durable:
        st.caption("Guarda toda la sesión en PostgreSQL y recupera Configuración General sin sobrescribir otras secciones activas.")
    else:
        st.warning(
            "Todavía usas SQLite, que también se borra al reiniciar en la mayoría de hostings. "
            "Configura `COPYMARY_DATABASE_URL` con PostgreSQL para que el respaldo sobreviva a un reinicio."
        )

    latest = latest_snapshot_info()
    if latest:
        st.caption(
            f"Último respaldo en la nube: {latest['created_at_utc'][:16].replace('T', ' ')} UTC · "
            f"{latest['sections_included']} sección(es) con datos · {latest['size_bytes'] / 1024:,.1f} KB"
        )
    else:
        st.caption("Todavía no se ha guardado ningún respaldo en la nube.")

    cloud_cols = st.columns(2)
    if cloud_cols[0].button("Guardar respaldo en la nube ahora", type="primary", use_container_width=True):
        saved = save_snapshot_to_database()
        st.success(f"Respaldo guardado ({saved['sections_included']} sección(es) con datos).")
        st.rerun()
    if cloud_cols[1].button(
        "Restaurar el más reciente de la nube", use_container_width=True,
        disabled=latest is None,
        help="Reemplaza los datos de esta sesión con el último respaldo guardado en la nube.",
    ):
        restored = restore_latest_snapshot_from_database()
        if restored:
            st.success("Sesión restaurada desde el respaldo en la nube.")
            st.rerun()

    st.divider()
    st.markdown("### Respaldo manual (archivo)")
    st.warning("Descarga este respaldo antes de cerrar la sesión para evitar perder datos.")
    _metrics({SECTION_LABELS[key]: _count(st.session_state.get(key)) for key in SESSION_KEYS})
    st.download_button(
        "Descargar respaldo general", data=_build_backup(),
        file_name="copymary_respaldo_sesion_v2.json", mime="application/json",
        type="primary", use_container_width=True,
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
                "Secciones que deseas restaurar", options=available, default=available,
                format_func=lambda key: SECTION_LABELS[key],
            )
            confirmation = st.checkbox("Entiendo que las secciones seleccionadas reemplazarán sus datos actuales.")
            if st.button(
                "Restaurar secciones seleccionadas", type="primary", use_container_width=True,
                disabled=not selected or not confirmation,
            ):
                _restore(restored, selected)
                st.success(f"Se restauraron {len(selected)} sección(es).")
                st.rerun()

    render_info_card(
        "Compatibilidad",
        "Los respaldos antiguos pueden restaurarse sin borrar las secciones nuevas que no existían en el archivo.",
        "RESPALDO V2",
    )
