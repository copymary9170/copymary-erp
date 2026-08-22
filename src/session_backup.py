"""Centro de respaldo general de CopyMary ERP.

Combina snapshots versionados de la sesión con gobierno operativo: permisos,
auditoría, integridad y un estado de salud visible. Los snapshots no sustituyen
un dump completo de PostgreSQL del servidor.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.auth import ADMIN_ROLE_NAME, current_user, permissions_for_role
from src.components import render_info_card, render_page_header
from src.erp_database import (
    connect,
    get_database_status,
    initialize_database,
    record_audit_event,
)

MAX_CLOUD_SNAPSHOTS = 30
BACKUP_VERSION = 3
BACKUP_MODULE = "backup"
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


def _actor_id() -> str:
    user = current_user()
    return user.user_id if user else ""


def has_backup_permission(action: str) -> bool:
    """Valida permisos sensibles con deny-by-default.

    Administrador conserva acceso total. Para otros roles se requiere una fila
    explícita en ``app_permissions`` para módulo ``backup`` y la acción pedida.
    ``backup.view`` solo permite abrir/consultar el centro; no habilita crear,
    descargar o restaurar.
    """
    user = current_user()
    if user is None:
        return False
    if user.role_name == ADMIN_ROLE_NAME:
        return True
    rows = permissions_for_role(user.role_id)
    return any(
        row.get("module_name") == BACKUP_MODULE
        and row.get("action_name") == action
        and bool(row.get("allowed"))
        for row in rows
    )


def _audit(action: str, snapshot_id: str = "", **details) -> None:
    record_audit_event(
        BACKUP_MODULE,
        "session_snapshots",
        snapshot_id or "current",
        action,
        after=details,
        actor_user_id=_actor_id(),
    )


def _serialize(value):
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [asdict(item) if is_dataclass(item) else item for item in value]
    return value


def _payload_data() -> dict:
    return {key: _serialize(st.session_state.get(key)) for key in SESSION_KEYS}


def _checksum(data: dict) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _backup_payload() -> dict:
    data = _payload_data()
    return {
        "backup_version": BACKUP_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "application": "CopyMary ERP",
        "checksum_sha256": _checksum(data),
        "data": data,
    }


def _build_backup() -> bytes:
    return json.dumps(_backup_payload(), ensure_ascii=False, indent=2).encode("utf-8")


def _friendly_filename(created_at_utc: str | None = None) -> str:
    raw = created_at_utc or datetime.now(timezone.utc).isoformat()
    safe = raw[:19].replace(":", "-").replace("T", "_")
    return f"CopyMary_Backup_{safe}_UTC.json"


def save_snapshot_to_database(audit: bool = True) -> dict:
    payload = _backup_payload()
    data_json = json.dumps(payload, ensure_ascii=False)
    size_bytes = len(data_json.encode("utf-8"))
    sections_included = sum(1 for value in payload["data"].values() if value)
    snapshot_id = f"SNAP-{uuid4().hex[:10].upper()}"
    created_at = payload["created_at_utc"]

    initialize_database()
    with connect() as conn:
        conn.execute(
            "INSERT INTO session_snapshots(snapshot_id, data_json, sections_included, size_bytes, created_at_utc) VALUES (?, ?, ?, ?, ?)",
            (snapshot_id, data_json, sections_included, size_bytes, created_at),
        )
        old_ids = [
            row["snapshot_id"]
            for row in conn.execute(
                "SELECT snapshot_id FROM session_snapshots ORDER BY created_at_utc DESC"
            ).fetchall()
        ][MAX_CLOUD_SNAPSHOTS:]
        for old_id in old_ids:
            conn.execute("DELETE FROM session_snapshots WHERE snapshot_id = ?", (old_id,))

    result = {
        "snapshot_id": snapshot_id,
        "sections_included": sections_included,
        "size_bytes": size_bytes,
        "created_at_utc": created_at,
        "checksum_sha256": payload["checksum_sha256"],
    }
    if audit:
        _audit("create", snapshot_id, sections_included=sections_included, size_bytes=size_bytes)
    return result


def list_snapshots(limit: int = MAX_CLOUD_SNAPSHOTS) -> list[dict]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(
            "SELECT snapshot_id, sections_included, size_bytes, created_at_utc FROM session_snapshots ORDER BY created_at_utc DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def latest_snapshot_info() -> dict | None:
    rows = list_snapshots(1)
    return rows[0] if rows else None


def _snapshot_row(snapshot_id: str) -> dict | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM session_snapshots WHERE snapshot_id = ? LIMIT 1",
            (snapshot_id,),
        ).fetchone()
    return dict(row) if row else None


def _latest_snapshot_row() -> dict | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM session_snapshots ORDER BY created_at_utc DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def snapshot_bytes(snapshot_id: str) -> bytes | None:
    row = _snapshot_row(snapshot_id)
    return row["data_json"].encode("utf-8") if row else None


def _audit_download(snapshot_id: str, size_bytes: int = 0) -> None:
    _audit("download", snapshot_id, size_bytes=size_bytes)


def restore_snapshot_from_database(snapshot_id: str, create_rollback: bool = True) -> dict | None:
    row = _snapshot_row(snapshot_id)
    if row is None:
        return None
    rollback_id = ""
    if create_rollback and session_has_data():
        rollback = save_snapshot_to_database(audit=False)
        rollback_id = rollback["snapshot_id"]
    restored = _parse_backup(row["data_json"].encode("utf-8"))
    selected = [key for key in SESSION_KEYS if key in restored["present_sections"]]
    _restore(restored, selected)
    _audit("restore", snapshot_id, rollback_snapshot_id=rollback_id, sections_restored=len(selected))
    return row


def restore_latest_snapshot_from_database() -> dict | None:
    row = _latest_snapshot_row()
    if row is None:
        return None
    return restore_snapshot_from_database(row["snapshot_id"])


def session_has_data() -> bool:
    return any(st.session_state.get(key) for key in SESSION_KEYS)


def restore_latest_snapshot_on_startup() -> None:
    """Restaura sin sobrescribir trabajo ya cargado."""
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
    if version not in {1, 2, 3}:
        raise ValueError("La versión del respaldo no es compatible.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("El respaldo no contiene datos válidos.")
    if version >= 3:
        expected = str(payload.get("checksum_sha256", ""))
        if not expected or expected != _checksum(data):
            raise ValueError("La verificación de integridad falló. El respaldo puede estar dañado o alterado.")

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


def backup_health(latest: dict | None = None, is_durable: bool | None = None) -> dict:
    """Devuelve un semáforo reutilizable para paneles y pruebas."""
    if latest is None:
        latest = latest_snapshot_info()
    if is_durable is None:
        is_durable = get_database_status().engine == "postgresql"
    if latest is None:
        return {"level": "red", "label": "Riesgo", "reason": "No existe ningún respaldo guardado.", "age_hours": None}
    try:
        created = datetime.fromisoformat(str(latest["created_at_utc"]).replace("Z", "+00:00"))
        age_hours = max(0.0, (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds() / 3600)
    except Exception:
        return {"level": "red", "label": "Riesgo", "reason": "La fecha del último respaldo es inválida.", "age_hours": None}
    if not is_durable:
        return {"level": "yellow", "label": "Atención", "reason": "Los snapshots están en SQLite y pueden ser efímeros en hosting.", "age_hours": age_hours}
    if age_hours <= 24:
        return {"level": "green", "label": "Protegido", "reason": "Existe un respaldo persistente de menos de 24 horas.", "age_hours": age_hours}
    if age_hours <= 168:
        return {"level": "yellow", "label": "Atención", "reason": "El último respaldo tiene más de 24 horas.", "age_hours": age_hours}
    return {"level": "red", "label": "Riesgo", "reason": "El último respaldo tiene más de 7 días.", "age_hours": age_hours}


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


def _status_message(latest: dict | None, is_durable: bool) -> None:
    health = backup_health(latest, is_durable)
    message = f"{health['label']}: {health['reason']}"
    if health["level"] == "green":
        st.success(f"🟢 {message}")
    elif health["level"] == "yellow":
        st.warning(f"🟡 {message}")
    else:
        st.error(f"🔴 {message}")


def render_session_backup() -> None:
    with st.container(border=True):
        render_page_header(
            "Respaldo general",
            "Protege, descarga y recupera la información principal de CopyMary ERP.",
        )
        st.caption("Incluye configuración, clientes, ventas, compras, caja, gastos, activos, inventario, producción, precios y metas.")

    if not has_backup_permission("view") and not has_backup_permission("create") and not has_backup_permission("restore") and not has_backup_permission("download"):
        st.error("No tienes permisos para consultar el centro de respaldos.")
        return

    can_create = has_backup_permission("create")
    can_download = has_backup_permission("download")
    can_restore = has_backup_permission("restore")

    db_status = get_database_status()
    is_durable = db_status.engine == "postgresql"
    latest = latest_snapshot_info()
    _status_message(latest, is_durable)

    st.markdown("### Estado de protección")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Motor", "PostgreSQL" if is_durable else "SQLite")
    c2.metric("Respaldos guardados", str(len(list_snapshots())))
    c3.metric("Último respaldo", latest["created_at_utc"][:16].replace("T", " ") + " UTC" if latest else "Nunca")
    c4.metric("Tamaño", f"{latest['size_bytes'] / 1024:,.1f} KB" if latest else "—")

    if not is_durable:
        st.warning(
            "SQLite sirve para desarrollo y pruebas, pero puede borrarse al reiniciar en algunos hostings. "
            "Configura `COPYMARY_DATABASE_URL` con PostgreSQL para que los snapshots sean persistentes."
        )

    action_cols = st.columns(2)
    if action_cols[0].button("Crear respaldo ahora", type="primary", use_container_width=True, disabled=not can_create):
        saved = save_snapshot_to_database()
        st.success(
            f"Respaldo {saved['snapshot_id']} creado y verificado: "
            f"{saved['sections_included']} sección(es), {saved['size_bytes'] / 1024:,.1f} KB."
        )
        st.rerun()
    current_backup = _build_backup()
    action_cols[1].download_button(
        "Descargar copia de seguridad",
        data=current_backup,
        file_name=_friendly_filename(),
        mime="application/json",
        use_container_width=True,
        disabled=not can_download,
        on_click=_audit_download if can_download else None,
        args=("current", len(current_backup)) if can_download else None,
    )

    st.divider()
    st.markdown("### Historial de respaldos")
    snapshots = list_snapshots()
    if not snapshots:
        st.caption("Todavía no hay respaldos guardados en la base de datos.")
    else:
        for snap in snapshots:
            with st.container(border=True):
                left, middle, right = st.columns((3, 2, 2))
                left.markdown(f"**{snap['created_at_utc'][:19].replace('T', ' ')} UTC**")
                left.caption(f"{snap['snapshot_id']} · {snap['sections_included']} sección(es)")
                middle.metric("Tamaño", f"{snap['size_bytes'] / 1024:,.1f} KB")
                payload = snapshot_bytes(snap["snapshot_id"])
                if payload:
                    middle.download_button(
                        "Descargar",
                        data=payload,
                        file_name=_friendly_filename(snap["created_at_utc"]),
                        mime="application/json",
                        key=f"download_{snap['snapshot_id']}",
                        use_container_width=True,
                        disabled=not can_download,
                        on_click=_audit_download if can_download else None,
                        args=(snap["snapshot_id"], snap["size_bytes"]) if can_download else None,
                    )
                selected = right.checkbox("Seleccionar", key=f"select_{snap['snapshot_id']}", disabled=not can_restore)
                confirmation = right.text_input(
                    "Escribe RESTAURAR",
                    key=f"confirm_{snap['snapshot_id']}",
                    disabled=not selected or not can_restore,
                )
                if right.button(
                    "Restaurar",
                    key=f"restore_{snap['snapshot_id']}",
                    disabled=not can_restore or not selected or confirmation.strip().upper() != "RESTAURAR",
                    use_container_width=True,
                ):
                    restore_snapshot_from_database(snap["snapshot_id"], create_rollback=True)
                    st.success("Respaldo restaurado. Se creó primero una copia de seguridad del estado anterior.")
                    st.rerun()

    st.divider()
    st.markdown("### Restaurar desde archivo")
    uploaded = st.file_uploader("Selecciona un respaldo JSON de CopyMary ERP", type=("json",), disabled=not can_restore)
    if uploaded is not None and can_restore:
        try:
            restored = _parse_backup(uploaded.getvalue())
        except (TypeError, ValueError) as exc:
            st.error(str(exc))
        else:
            present = restored["present_sections"]
            st.success("✅ Archivo válido, compatible e íntegro.")
            st.caption(f"Fecha UTC: {restored['created_at_utc']}")
            available = [key for key in SESSION_KEYS if key in present]
            _metrics({SECTION_LABELS[key]: _count(restored[key]) for key in available})
            selected = st.multiselect(
                "Secciones que deseas restaurar", options=available, default=available,
                format_func=lambda key: SECTION_LABELS[key],
            )
            confirmation = st.text_input("Escribe RESTAURAR para confirmar", key="restore_file_confirmation")
            if st.button(
                "Restaurar secciones seleccionadas", type="primary", use_container_width=True,
                disabled=not selected or confirmation.strip().upper() != "RESTAURAR",
            ):
                rollback_id = ""
                if session_has_data():
                    rollback_id = save_snapshot_to_database(audit=False)["snapshot_id"]
                _restore(restored, selected)
                _audit("restore_file", "uploaded", rollback_snapshot_id=rollback_id, sections_restored=len(selected))
                st.success(f"Se restauraron {len(selected)} sección(es) y se guardó una copia previa del estado actual.")
                st.rerun()

    st.divider()
    st.markdown("### Contenido del respaldo actual")
    _metrics({SECTION_LABELS[key]: _count(st.session_state.get(key)) for key in SESSION_KEYS})

    render_info_card(
        "Compatibilidad e integridad",
        "Los respaldos V3 incluyen SHA-256 para detectar archivos dañados o alterados. "
        "Crear, descargar y restaurar también queda sujeto a permisos y auditoría.",
        "RESPALDO V3",
    )
