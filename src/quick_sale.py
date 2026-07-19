"""Venta rápida de mostrador para CopyMary ERP.

Gap detectado pensando específicamente en el negocio de CopyMary (imprime,
saca copias, sublima, papelería creativa, encuadernación, toppers, insumos
escolares/oficina): `commercial.py` (render_sales) exige seleccionar un
cliente ya registrado antes de vender. Eso es correcto para pedidos
personalizados con seguimiento, pero es fricción real para el volumen más
alto del día a día de una papelería: alguien que compra 5 fotocopias o un
cuaderno no tiene por qué registrarse como cliente.

Este módulo agrega dos cosas:
1. Un tarifario configurable de servicios de mostrador (fotocopia B/N,
   color, impresión, plastificado, anillado, escaneo, etc.) para que quien
   cobra no tenga que recordar precios de memoria.
2. Un formulario de venta rápida sin cliente obligatorio: si no se elige un
   cliente existente, se usa/crea automáticamente un registro "Cliente
   ocasional" (una sola vez, se reutiliza siempre).

Escribe en las mismas tablas de siempre (sales_registry, cash_movements,
customers_registry, con exactamente los mismos campos que usa
commercial.py) para que el Estado de Resultados, el flujo de caja, las
comisiones, y todo lo demás lo vean automáticamente sin cambios.
"""

from __future__ import annotations

from uuid import uuid4

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database
from src.money import format_money, get_currency
from src.payment_fees import sale_breakdown, should_apply_igtf
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save

WALK_IN_CLIENT_NAME = "Cliente ocasional"
SERVICE_CATEGORIES = (
    "Fotocopiado", "Impresión", "Escaneo", "Acabados",
    "Redacción y trámites", "Personalizados", "Otro",
)
PAYMENT_METHODS = ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro")

DEFAULT_SERVICES = (
    ("Fotocopia B/N", "Fotocopiado", 0.05, "por página"),
    ("Fotocopia color", "Fotocopiado", 0.20, "por página"),
    ("Impresión B/N", "Impresión", 0.05, "por página"),
    ("Impresión color", "Impresión", 0.25, "por página"),
    ("Escaneo", "Escaneo", 0.10, "por página"),
    ("Plastificado carta", "Acabados", 0.50, "por unidad"),
    ("Anillado", "Acabados", 1.50, "por unidad"),
)

# Servicios sugeridos adicionales del día a día de una papelería: redacción de
# documentos, trámites y personalizados. Son solo un punto de partida — los
# precios se ajustan a la realidad del negocio desde el Tarifario. Se agregan
# con un botón (los que falten), nunca sobreescriben los ya cargados.
SUGGESTED_SERVICES = (
    *DEFAULT_SERVICES,
    ("Carta de trabajo / constancia", "Redacción y trámites", 3.00, "por documento"),
    ("Transcripción de documento", "Redacción y trámites", 1.00, "por página"),
    ("Redacción de currículum", "Redacción y trámites", 5.00, "por documento"),
    ("Redacción de carta / oficio", "Redacción y trámites", 3.00, "por documento"),
    ("Llenado de planilla / formulario", "Redacción y trámites", 2.00, "por planilla"),
    ("Impresión de foto tipo carnet", "Impresión", 1.50, "por plancha"),
    ("Impresión de esténcil (tatuaje)", "Impresión", 2.00, "por esténcil"),
    ("Impresión de carnet PVC", "Personalizados", 4.00, "por carnet"),
    ("Sublimación de taza", "Personalizados", 6.00, "por taza"),
    ("Sublimación de franela", "Personalizados", 8.00, "por prenda"),
    ("DTF en prenda", "Personalizados", 7.00, "por prenda"),
    ("Corte de vinil (Cameo)", "Personalizados", 3.00, "por diseño"),
    ("Aplicación de foil", "Acabados", 2.00, "por hoja"),
    ("Encuadernado empastado", "Acabados", 6.00, "por unidad"),
    ("Grabado láser", "Personalizados", 5.00, "por pieza"),
    ("Impresión 3D", "Personalizados", 10.00, "por pieza"),
)


# ---------------------------------------------------------------------------
# Cálculo puro (testeable sin base de datos)
# ---------------------------------------------------------------------------

def line_total(quantity: float, unit_price: float, discount: float = 0.0) -> float:
    return max((float(quantity) * float(unit_price)) - float(discount), 0.0)


def find_walk_in_client(clients: list[dict]) -> dict | None:
    for client in clients:
        if client.get("name") == WALK_IN_CLIENT_NAME:
            return client
    return None


def build_sale_record(client_id: str, description: str, quantity: float, unit_price: float, discount: float, payment_method: str, notes: str = "", apply_igtf: bool = False, apply_iva: bool = False) -> dict:
    subtotal = line_total(quantity, unit_price, discount)
    # El IVA se suma al subtotal para obtener lo que realmente paga el
    # cliente (total); la comisión del medio de pago y el IGTF, en cambio,
    # se descuentan de ese total para saber cuánto queda neto en caja/banco.
    # IVA e IGTF son siempre decisión manual — hay ventas exentas de uno o
    # de ambos según el caso, nunca se infieren solo del medio de pago.
    breakdown = sale_breakdown(subtotal, payment_method, apply_iva=apply_iva, apply_igtf=apply_igtf)
    return {
        "sale_id": uuid4().hex[:10],
        "created_at_utc": _now(),
        "client_id": client_id,
        "description": description.strip(),
        "quantity": float(quantity),
        "unit_price": float(unit_price),
        "discount": float(discount),
        "subtotal": breakdown["subtotal"],
        "total": breakdown["total"],
        "estimated_cost": 0.0,
        "payment_status": "Pagado",
        "order_status": "Entregado",
        "payment_method": payment_method,
        "notes": notes.strip(),
        "cash_registered": True,
        "iva_applied": breakdown["iva_applied"],
        "iva_rate": breakdown["iva_rate"],
        "iva_amount": breakdown["iva_amount"],
        "payment_fee_rate": breakdown["fee_rate"],
        "payment_fee_amount": breakdown["fee_amount"],
        "igtf_applied": breakdown["igtf_applied"],
        "igtf_amount": breakdown["igtf_amount"],
        "net_amount": breakdown["net_amount"],
    }


def build_cash_movement_record(sale: dict) -> dict:
    return {
        "movement_id": uuid4().hex[:10],
        "created_at_utc": _now(),
        "movement_type": "Ingreso",
        "category": "Venta",
        "amount": sale["total"],
        "payment_method": sale["payment_method"],
        "reference": sale["sale_id"],
        "notes": sale["description"],
    }


# ---------------------------------------------------------------------------
# Tarifario (base de datos)
# ---------------------------------------------------------------------------

def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def list_services(active_only: bool = True) -> list[dict]:
    if active_only:
        return _fetch_all("SELECT * FROM quick_service_prices WHERE active = 1 ORDER BY category, name")
    return _fetch_all("SELECT * FROM quick_service_prices ORDER BY category, name")


def create_service(name: str, category: str, unit_price: float, unit_label: str) -> str:
    initialize_database()
    service_id = f"SVC-{uuid4().hex[:8].upper()}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO quick_service_prices(service_id, name, category, unit_price, unit_label, active, created_at_utc) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (service_id, name.strip(), category, unit_price, unit_label.strip(), _now()),
        )
    return service_id


def seed_default_services_if_empty() -> None:
    """Carga el tarifario típico de una papelería/centro de copiado la
    primera vez, para que el mostrador no arranque vacío. No hace nada si
    ya existe al menos un servicio (no sobreescribe precios editados)."""
    if list_services(active_only=False):
        return
    for name, category, unit_price, unit_label in DEFAULT_SERVICES:
        create_service(name, category, unit_price, unit_label)


def missing_suggested_services() -> list[tuple[str, str, float, str]]:
    """Servicios del catálogo sugerido que todavía NO existen en el tarifario
    (comparando por nombre, insensible a mayúsculas). Permite ofrecerle al
    usuario cargar solo los que faltan, sin duplicar ni tocar los precios de
    los que ya configuró."""
    existing_names = {str(row.get("name", "")).casefold() for row in list_services(active_only=False)}
    return [service for service in SUGGESTED_SERVICES if service[0].casefold() not in existing_names]


def add_missing_suggested_services() -> int:
    """Agrega al tarifario los servicios sugeridos que falten. Devuelve
    cuántos se agregaron."""
    missing = missing_suggested_services()
    for name, category, unit_price, unit_label in missing:
        create_service(name, category, unit_price, unit_label)
    return len(missing)


def set_service_active(service_id: str, active: bool) -> None:
    initialize_database()
    with connect() as conn:
        conn.execute("UPDATE quick_service_prices SET active = ? WHERE service_id = ?", (1 if active else 0, service_id))


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def _ensure_walk_in_client(clients: list[dict]) -> tuple[str, list[dict]]:
    existing = find_walk_in_client(clients)
    if existing:
        return str(existing["client_id"]), clients
    new_client = {
        "client_id": uuid4().hex[:10],
        "name": WALK_IN_CLIENT_NAME,
        "client_type": "Persona",
        "phone": "",
        "email": "",
        "address": "",
        "notes": "Cliente genérico para ventas rápidas de mostrador sin registro individual.",
        "created_at_utc": _now(),
    }
    updated = [*clients, new_client]
    _save("customers_registry", updated)
    return new_client["client_id"], updated


def render_quick_sale() -> None:
    render_page_header("Venta rápida de mostrador", "Cobra fotocopias, impresiones y ventas sueltas sin registrar cliente.")
    seed_default_services_if_empty()

    clients = _rows("customers_registry")
    services = list_services()
    currency = get_currency()

    sale_tab, prices_tab = st.tabs(("Vender", "Tarifario"))

    with sale_tab:
        client_options = {WALK_IN_CLIENT_NAME: None, **{c["name"]: c["client_id"] for c in clients if c.get("name") != WALK_IN_CLIENT_NAME}}
        service_options = {"— Línea manual —": None, **{f"{s['name']} ({format_money(s['unit_price'], currency)} {s['unit_label']})": s for s in services}}

        selected_client_label = st.selectbox("Cliente", tuple(client_options.keys()), help="Deja 'Cliente ocasional' para ventas de mostrador sin registro.")
        selected_service_label = st.selectbox("Servicio del tarifario (opcional)", tuple(service_options.keys()))
        selected_service = service_options[selected_service_label]

        with st.form("quick_sale_form", clear_on_submit=True):
            description = st.text_input("Descripción", value=selected_service["name"] if selected_service else "")
            cols = st.columns(3)
            quantity = cols[0].number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
            unit_price = cols[1].number_input("Precio unitario", min_value=0.0, value=float(selected_service["unit_price"]) if selected_service else 0.0, step=0.05)
            discount = cols[2].number_input("Descuento", min_value=0.0, value=0.0, step=0.5)
            payment_method = st.selectbox("Método de pago", PAYMENT_METHODS)
            iva_col, igtf_col = st.columns(2)
            with iva_col:
                apply_iva = st.checkbox("Esta venta cobra IVA", value=False, help="Decisión manual: márcalo solo si esta venta específica debe facturar IVA.")
            with igtf_col:
                apply_igtf = st.checkbox(
                    "Esta venta paga IGTF",
                    value=should_apply_igtf(payment_method),
                    help="Decisión manual: márcalo solo si esta operación específica paga IGTF. Se sugiere marcado para pagos en divisas/cripto, pero hay casos exentos — confírmalo tú.",
                )
            subtotal_now = line_total(quantity, unit_price, discount)
            preview = sale_breakdown(subtotal_now, payment_method, apply_iva=apply_iva, apply_igtf=apply_igtf)
            st.metric("Total a cobrar", format_money(preview["total"], currency))
            note_parts = []
            if preview["iva_applied"]:
                note_parts.append(f"IVA ({preview['iva_rate']:.1f}%): {format_money(preview['iva_amount'], currency)}")
            if preview["fee_amount"] > 0:
                note_parts.append(f"Comisión {payment_method}: {format_money(preview['fee_amount'], currency)}")
            if preview["igtf_applied"]:
                note_parts.append(f"IGTF: {format_money(preview['igtf_amount'], currency)}")
            if note_parts:
                st.caption(" · ".join(note_parts) + f" → Neto real: {format_money(preview['net_amount'], currency)}")
            submitted = st.form_submit_button("Cobrar", type="primary", use_container_width=True)

        if submitted:
            if not description.strip():
                st.error("La descripción es obligatoria.")
            elif line_total(quantity, unit_price, discount) <= 0:
                st.error("El total debe ser mayor que cero.")
            else:
                client_id = client_options[selected_client_label]
                if client_id is None:
                    client_id, clients = _ensure_walk_in_client(clients)
                sale = build_sale_record(client_id, description, quantity, unit_price, discount, payment_method, apply_igtf=apply_igtf, apply_iva=apply_iva)
                sales = _rows("sales_registry")
                sales.append(sale)
                _save("sales_registry", sales)
                cash = _rows("cash_movements")
                cash.append(build_cash_movement_record(sale))
                _save("cash_movements", cash)
                st.success(
                    f"Venta registrada: {format_money(sale['total'], currency)}"
                    + (f" (neto real: {format_money(sale['net_amount'], currency)})" if sale["net_amount"] != sale["total"] else "")
                )
                st.rerun()

    with prices_tab:
        st.caption("Los precios se cargan una vez con valores típicos de papelería/centro de copiado; edítalos según tu negocio.")
        missing = missing_suggested_services()
        if missing:
            st.info(
                f"Hay {len(missing)} servicio(s) sugeridos de papelería que aún no están en tu tarifario "
                "(cartas de trabajo, transcripción, sublimación, DTF, carnets PVC, esténciles...). "
                "Los precios son solo de partida — ajústalos a tu realidad después de cargarlos."
            )
            if st.button("Cargar servicios sugeridos que faltan", use_container_width=True):
                added = add_missing_suggested_services()
                st.success(f"{added} servicio(s) agregados al tarifario.")
                st.rerun()

        with st.expander("Agregar servicio al tarifario"):
            with st.form("service_form", clear_on_submit=True):
                cols = st.columns(4)
                name = cols[0].text_input("Nombre")
                category = cols[1].selectbox("Categoría", SERVICE_CATEGORIES)
                unit_price = cols[2].number_input("Precio", min_value=0.0, step=0.05)
                unit_label = cols[3].text_input("Unidad", value="por unidad")
                submitted_service = st.form_submit_button("Agregar", type="primary", use_container_width=True)
            if submitted_service:
                if not name.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    create_service(name, category, unit_price, unit_label)
                    st.success(f"'{name}' agregado al tarifario.")
                    st.rerun()

        all_services = list_services(active_only=False)
        for service in all_services:
            with st.container(border=True):
                cols = st.columns([3, 2, 1])
                cols[0].markdown(f"**{service['name']}** · {service['category']}")
                cols[1].write(f"{format_money(service['unit_price'], currency)} {service['unit_label']}")
                is_active = bool(service.get("active"))
                if cols[2].button("Desactivar" if is_active else "Activar", key=f"toggle_{service['service_id']}"):
                    set_service_active(service["service_id"], not is_active)
                    st.rerun()

    render_info_card("Alcance", "Venta rápida sin cliente obligatorio, con tarifario configurable. Se integra automáticamente con reportes existentes (ventas, caja, comisiones).", "MOSTRADOR")


app_shell.FUNCTIONAL_MODULES["Venta rápida de mostrador"] = render_quick_sale
