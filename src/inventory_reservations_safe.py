"""Vista segura de reservas de Inventario, fase 5.

Mantiene la estructura actual de ``inventory_reservations`` y añade acciones
controladas para liberar o consumir una reserva completa con trazabilidad.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src import inventory_enterprise
from src.session_utils import read_list, save_list


RESERVATION_SOURCES = ("Pedido", "Producción", "Cotización", "Uso interno", "Otro")


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reserved_for(item_id: str, reservations: list[dict]) -> float:
    return sum(
        _num(row.get("quantity"))
        for row in reservations
        if str(row.get("item_id")) == str(item_id) and row.get("status") == "Activa"
    )


def render_inventory_reservations_safe(rows: list[dict]) -> None:
    """Crea, libera y consume reservas sin alterar su esquema histórico."""
    reservations = [dict(row) for row in read_list("inventory_reservations")]
    active_items = [row for row in rows if row.get("active", True)]
    by_id = {str(row.get("item_id")): row for row in rows}

    st.caption(
        "Una reserva aparta existencia sin descontarla físicamente. Solo al consumirla "
        "se genera una salida del inventario."
    )

    if active_items:
        labels = {}
        for row in active_items:
            item_id = str(row.get("item_id"))
            physical = _num(row.get("available_quantity"))
            reserved = _reserved_for(item_id, reservations)
            available = max(physical - reserved, 0.0)
            labels[
                f"{row.get('name')} · físico {physical:,.2f} · reservado {reserved:,.2f} · disponible {available:,.2f} {row.get('unit_name', '')}"
            ] = row

        with st.form("inventory_safe_reservation_create", clear_on_submit=True):
            selected = st.selectbox("Artículo", tuple(labels))
            item = labels[selected]
            item_id = str(item.get("item_id"))
            free = max(
                _num(item.get("available_quantity")) - _reserved_for(item_id, reservations),
                0.0,
            )
            a, b, c = st.columns(3)
            quantity = a.number_input(
                "Cantidad a reservar",
                min_value=0.0,
                max_value=float(free),
                value=0.0,
                step=1.0,
            )
            source = b.selectbox("Origen", RESERVATION_SOURCES)
            due_date = c.date_input("Vence", value=date.today())
            a, b = st.columns(2)
            reference = a.text_input("Referencia obligatoria")
            responsible = b.text_input("Responsable")
            create = st.form_submit_button("Crear reserva", type="primary", use_container_width=True)

        if create:
            if quantity <= 0:
                st.error("La cantidad a reservar debe ser mayor que cero.")
            elif quantity > free:
                st.error("La reserva supera la existencia disponible.")
            elif not reference.strip():
                st.error("Debes indicar una referencia para la reserva.")
            else:
                reservations.append({
                    "reservation_id": f"RSV-{uuid4().hex[:8].upper()}",
                    "item_id": item_id,
                    "quantity": float(quantity),
                    "source": source,
                    "reference": reference.strip(),
                    "due_date": due_date.isoformat(),
                    "responsible": responsible.strip() or "Sin asignar",
                    "note": "",
                    "status": "Activa",
                    "created_at_utc": _now(),
                })
                save_list("inventory_reservations", reservations)
                st.success("Reserva creada. La existencia disponible se actualizó sin descontar stock físico.")
                st.rerun()
    else:
        st.info("No hay artículos activos para reservar.")

    active_reservations = [row for row in reservations if row.get("status") == "Activa"]
    if not active_reservations:
        st.info("No hay reservas activas.")
    else:
        st.markdown("#### Reservas activas")
        table = []
        for reservation in reversed(active_reservations):
            item = by_id.get(str(reservation.get("item_id")), {})
            physical = _num(item.get("available_quantity"))
            total_reserved = _reserved_for(str(reservation.get("item_id")), reservations)
            table.append({
                "Reserva": reservation.get("reservation_id"),
                "Artículo": item.get("name") or "Material no disponible",
                "Cantidad": _num(reservation.get("quantity")),
                "Físico": physical,
                "Reservado total": total_reserved,
                "Disponible": max(physical - total_reserved, 0.0),
                "Origen": reservation.get("source", ""),
                "Referencia": reservation.get("reference", ""),
                "Responsable": reservation.get("responsible", ""),
                "Vence": reservation.get("due_date", ""),
            })
        st.dataframe(table, use_container_width=True, hide_index=True)

        action_labels = {
            f"{row.get('reservation_id')} · {by_id.get(str(row.get('item_id')), {}).get('name', 'Material')} · {_num(row.get('quantity')):,.2f}": row
            for row in active_reservations
        }
        with st.form("inventory_safe_reservation_action"):
            selected_action = st.selectbox("Reserva a gestionar", tuple(action_labels))
            action = st.selectbox("Acción", ("Liberar", "Consumir completamente"))
            note = st.text_input("Responsable / motivo obligatorio")
            confirm = st.checkbox("Confirmo esta acción sobre la reserva seleccionada")
            apply_action = st.form_submit_button("Aplicar acción", type="primary", use_container_width=True)

        if apply_action:
            reservation = action_labels[selected_action]
            if not note.strip():
                st.error("Debes indicar responsable o motivo.")
                return
            if not confirm:
                st.error("Debes confirmar expresamente la acción.")
                return

            item = by_id.get(str(reservation.get("item_id")))
            quantity = _num(reservation.get("quantity"))
            if action == "Consumir completamente":
                if item is None:
                    st.error("El artículo de esta reserva ya no existe en Inventario.")
                    return
                if quantity > _num(item.get("available_quantity")):
                    st.error("La existencia física ya no alcanza para consumir esta reserva.")
                    return
                inventory_enterprise._movement(
                    item,
                    "Salida",
                    quantity,
                    f"Consumo reserva {reservation.get('reservation_id')}: {note.strip()}",
                )
                inventory_enterprise._save(rows)
                new_status = "Consumida"
                timestamp_field = "consumed_at_utc"
            else:
                new_status = "Liberada"
                timestamp_field = "released_at_utc"

            updated = []
            for row in reservations:
                current = dict(row)
                if current.get("reservation_id") == reservation.get("reservation_id"):
                    current["status"] = new_status
                    current[timestamp_field] = _now()
                    current["closed_by_or_reason"] = note.strip()
                updated.append(current)
            save_list("inventory_reservations", updated)
            st.success(f"Reserva {new_status.lower()} con trazabilidad.")
            st.rerun()

    history = list(reversed(reservations[-200:]))
    if history:
        st.markdown("#### Historial de reservas")
        st.dataframe(
            [{
                "Reserva": row.get("reservation_id", ""),
                "Artículo": by_id.get(str(row.get("item_id")), {}).get("name", "Material no disponible"),
                "Cantidad": row.get("quantity", 0),
                "Estado": row.get("status", ""),
                "Origen": row.get("source", ""),
                "Referencia": row.get("reference", ""),
                "Responsable": row.get("responsible", ""),
                "Creada": row.get("created_at_utc", ""),
                "Cierre": row.get("consumed_at_utc") or row.get("released_at_utc") or "—",
            } for row in history],
            use_container_width=True,
            hide_index=True,
        )
