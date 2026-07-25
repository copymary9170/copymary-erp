"""Edición controlada de ubicación, lote y vencimiento.

No permite cambiar existencias ni costos. Cada modificación queda registrada en un
historial separado de auditoría.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src import inventory_enterprise
from src.inventory_action_permissions import can_inventory_action, require_inventory_action
from src.inventory_lots_safe import render_inventory_stock_with_lots
from src.session_utils import read_list, save_list


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_inventory_stock_with_metadata_editor(rows: list[dict]) -> None:
    """Conserva Existencias y añade edición segura de metadatos logísticos."""
    render_inventory_stock_with_lots(rows)

    can_edit = can_inventory_action("metadata_edit")
    st.markdown("#### Actualizar ubicación, lote o vencimiento")
    st.caption("Esta acción no modifica existencia, costo promedio, reservas ni movimientos.")
    if not can_edit:
        st.warning("Tu rol puede consultar los datos logísticos, pero no modificarlos.")

    active = [row for row in rows if row.get("active", True)]
    if not active:
        st.info("No hay artículos activos para actualizar.")
        return

    labels = {
        f"{row.get('name', 'Artículo')} · {row.get('sku') or row.get('item_id')}": row
        for row in active
    }
    selected = st.selectbox("Artículo", tuple(labels), key="inventory_metadata_item")
    item = labels[selected]
    current_expiry = str(item.get("expiry_date") or item.get("expiry") or "")
    try:
        expiry_default = date.fromisoformat(current_expiry) if current_expiry else None
    except ValueError:
        expiry_default = None

    with st.form("inventory_metadata_safe_form"):
        a, b, c = st.columns(3)
        location = a.text_input("Ubicación", value=str(item.get("location") or ""), disabled=not can_edit)
        lot = b.text_input("Lote", value=str(item.get("lot") or ""), disabled=not can_edit)
        expiry = c.date_input("Vencimiento", value=expiry_default, disabled=not can_edit)
        reason = st.text_input("Motivo / responsable obligatorio", disabled=not can_edit)
        confirm = st.checkbox(
            "Confirmo que solo actualizaré datos logísticos del artículo",
            disabled=not can_edit,
        )
        submit = st.form_submit_button(
            "Guardar cambio auditado", type="primary", use_container_width=True,
            disabled=not can_edit,
        )

    if submit:
        try:
            require_inventory_action("metadata_edit")
        except PermissionError as exc:
            st.error(str(exc))
            return
        if not reason.strip():
            st.error("Debes indicar el motivo o responsable del cambio.")
            return
        if not confirm:
            st.error("Debes confirmar expresamente la actualización.")
            return

        new_values = {
            "location": location.strip(),
            "lot": lot.strip(),
            "expiry_date": expiry.isoformat() if expiry else "",
        }
        old_values = {
            "location": str(item.get("location") or ""),
            "lot": str(item.get("lot") or ""),
            "expiry_date": current_expiry,
        }
        changes = {
            field: {"before": old_values[field], "after": new_values[field]}
            for field in new_values if old_values[field] != new_values[field]
        }
        if not changes:
            st.info("No hay cambios para guardar.")
            return

        item.update(new_values)
        item["metadata_updated_at_utc"] = _now()
        inventory_enterprise._save(rows)

        audit = read_list("inventory_metadata_audit")
        audit.append({
            "audit_id": f"IMA-{uuid4().hex[:8].upper()}",
            "item_id": item.get("item_id"), "item_name": item.get("name"),
            "changes": changes, "reason": reason.strip(), "created_at_utc": _now(),
        })
        save_list("inventory_metadata_audit", audit)
        st.success("Datos logísticos actualizados con auditoría.")
        st.rerun()

    audit = list(reversed(read_list("inventory_metadata_audit")[-50:]))
    if audit:
        with st.expander("Historial de cambios logísticos"):
            st.dataframe([
                {
                    "Fecha": row.get("created_at_utc", ""),
                    "Artículo": row.get("item_name", ""),
                    "Motivo / responsable": row.get("reason", ""),
                    "Cambios": "; ".join(
                        f"{field}: {values.get('before', '') or '—'} → {values.get('after', '') or '—'}"
                        for field, values in row.get("changes", {}).items()
                    ),
                }
                for row in audit
            ], use_container_width=True, hide_index=True)
