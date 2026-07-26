"""Kardex valorizado y transferencias entre ubicaciones — CopyMary ERP.

Página autocontenida (Streamlit multipágina): se activa solo con colocarla en
`pages/`; no requiere cablear app.py ni la navegación.

- Kardex valorizado: historial cronológico de movimientos de un artículo con
  entradas, salidas, saldo acumulado, costo unitario y valor.
- Transferencias: mueve existencia de una ubicación a otra registrando dos
  movimientos (salida en origen + entrada en destino) que se netean en cero,
  para no alterar el stock total y conservar la trazabilidad.

Lee/guarda en `inventory_movements` (ya incluido en el respaldo general). Lectura
defensiva tolerante a esquema.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import streamlit as st

try:
    from src.session_utils import read_list as _read_list, save_list as _save_list
except Exception:  # pragma: no cover
    def _read_list(key: str) -> list[dict]:
        value = st.session_state.get(key, [])
        return value if isinstance(value, list) else []

    def _save_list(key: str, rows: list[dict]) -> None:
        st.session_state[key] = rows


MOVEMENTS_KEY = "inventory_movements"
INVENTORY_KEY = "inventory_registry"

TRANSFER_OUT = "Transferencia de salida"
TRANSFER_IN = "Transferencia de entrada"

_POSITIVE = {"entrada", "entrada por recepción de compra", "ajuste positivo",
             "devolución", "devolucion", TRANSFER_IN.lower()}
_NEGATIVE = {"salida", "ajuste negativo", "merma", "daño", "dano", "consumo interno",
             "devolución a proveedor", "devolucion a proveedor", TRANSFER_OUT.lower()}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(row: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def _is_positive(movement_type: str) -> bool:
    return str(movement_type or "").strip().lower() in _POSITIVE


def _is_negative(movement_type: str) -> bool:
    return str(movement_type or "").strip().lower() in _NEGATIVE


def _items() -> dict[str, dict]:
    """Etiqueta legible -> ítem de inventario."""
    options: dict[str, dict] = {}
    for row in _read_list(INVENTORY_KEY):
        item_id = str(_first(row, "item_id", "sku", default=""))
        name = _first(row, "name", "product_name", default="Material")
        sku = _first(row, "sku", "item_id", default="")
        label = f"{name} · {sku or item_id}"
        options[label] = row
    return options


def _kardex(item_id: str) -> tuple[list[dict], float, float]:
    """Movimientos del artículo con saldo y valor acumulados."""
    movements = [
        m for m in _read_list(MOVEMENTS_KEY)
        if str(_first(m, "item_id", "catalog_item_id", default="")) == item_id
    ]
    movements.sort(key=lambda m: str(_first(m, "created_at_utc", "created_at", "date", default="")))
    rows: list[dict] = []
    balance = 0.0
    last_cost = 0.0
    for m in movements:
        qty = _num(_first(m, "quantity", default=0.0))
        mtype = str(_first(m, "movement_type", "type", default=""))
        unit_cost = _num(_first(m, "unit_cost", default=0.0))
        if unit_cost > 0:
            last_cost = unit_cost
        entrada = qty if _is_positive(mtype) else 0.0
        salida = qty if _is_negative(mtype) else 0.0
        balance += entrada - salida
        rows.append({
            "Fecha": str(_first(m, "created_at_utc", "created_at", "date", default=""))[:19],
            "Movimiento": mtype,
            "Entrada": round(entrada, 2),
            "Salida": round(salida, 2),
            "Saldo": round(balance, 2),
            "Costo unit.": round(unit_cost, 4),
            "Ubicación": _first(m, "location", default=""),
            "Lote": _first(m, "lot", default=""),
            "Motivo": _first(m, "reason", default=""),
        })
    return rows, balance, balance * last_cost


def register_transfer(*, item: dict, origin: str, destination: str, quantity: float,
                      note: str = "") -> list[dict]:
    """Registra la transferencia como salida en origen + entrada en destino."""
    movements = _read_list(MOVEMENTS_KEY)
    item_id = str(_first(item, "item_id", "sku", default=""))
    name = _first(item, "name", "product_name", default="Material")
    unit_cost = _num(_first(item, "unit_cost", default=0.0))
    transfer_id = uuid4().hex[:8].upper()
    common = {
        "item_id": item_id,
        "catalog_item_id": _first(item, "catalog_item_id", default=""),
        "item_name": name,
        "quantity": float(quantity),
        "unit_cost": unit_cost,
        "transfer_id": transfer_id,
        "created_at_utc": _now(),
    }
    movements.append({**common, "movement_id": f"MOV-{uuid4().hex[:8].upper()}",
                      "movement_type": TRANSFER_OUT, "location": origin,
                      "reason": f"Transferencia a {destination}. {note}".strip()})
    movements.append({**common, "movement_id": f"MOV-{uuid4().hex[:8].upper()}",
                      "movement_type": TRANSFER_IN, "location": destination,
                      "reason": f"Transferencia desde {origin}. {note}".strip()})
    _save_list(MOVEMENTS_KEY, movements)
    return movements


def render() -> None:
    st.title("Kardex valorizado y transferencias")
    st.caption("Historial valorizado por artículo y movimientos entre ubicaciones.")

    items = _items()
    if not items:
        st.info("No hay artículos de inventario todavía. Regístralos en Inventario o "
                "recibe mercancía en Recepción.")
        return

    tab_kardex, tab_transfer = st.tabs(("📒 Kardex valorizado", "🔁 Transferencia"))

    with tab_kardex:
        label = st.selectbox("Artículo", tuple(items), key="kardex_item")
        item = items[label]
        item_id = str(_first(item, "item_id", "sku", default=""))
        rows, balance, value = _kardex(item_id)
        cols = st.columns(3)
        cols[0].metric("Saldo actual", f"{balance:,.2f} {_first(item, 'unit_name', default='')}")
        cols[1].metric("Costo unitario", f"{_num(_first(item, 'unit_cost', default=0.0)):,.4f}")
        cols[2].metric("Valor del saldo", f"{value:,.2f}")
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("Este artículo aún no tiene movimientos registrados.")

    with tab_transfer:
        st.caption("La transferencia no cambia el stock total; solo mueve existencia entre "
                   "ubicaciones y queda registrada en el kardex.")
        label_t = st.selectbox("Artículo a transferir", tuple(items), key="transfer_item")
        item_t = items[label_t]
        current_location = _first(item_t, "location", default="Almacén principal")
        with st.form("inventory_transfer_form", clear_on_submit=True):
            cols = st.columns(2)
            origin = cols[0].text_input("Desde (ubicación origen)", value=str(current_location))
            destination = cols[1].text_input("Hacia (ubicación destino)", value="")
            quantity = st.number_input("Cantidad a transferir", min_value=0.0, value=0.0, step=1.0)
            note = st.text_input("Nota (opcional)", max_chars=120)
            submitted = st.form_submit_button("Registrar transferencia", type="primary",
                                              use_container_width=True)
        if submitted:
            available = _num(_first(item_t, "available_quantity", "quantity", "stock", default=0.0))
            if quantity <= 0:
                st.error("La cantidad a transferir debe ser mayor que cero.")
            elif not destination.strip():
                st.error("Indica la ubicación destino.")
            elif origin.strip().casefold() == destination.strip().casefold():
                st.error("El origen y el destino no pueden ser iguales.")
            elif quantity > available:
                st.error(f"No puedes transferir más de la existencia disponible ({available:,.2f}).")
            else:
                register_transfer(item=item_t, origin=origin.strip(),
                                  destination=destination.strip(), quantity=float(quantity),
                                  note=note.strip())
                st.success(f"Transferencia registrada: {quantity:,.2f} de '{origin.strip()}' "
                           f"a '{destination.strip()}'.")
                st.rerun()


render()
