"""Cotizaciones orientadas por procesos y activos productivos."""

from uuid import uuid4

import streamlit as st

from src.assets import _get_assets
from src.components import render_page_header
from src.money import format_money
from src.production_processes import (
    PROCESS_OPTIONS,
    assets_for_processes,
    equipment_cost_for_processes,
    normalize_process_codes,
    process_coverage,
    process_labels,
)
from src.session_utils import now_iso as _now


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, rows: list[dict]) -> None:
    st.session_state[key] = rows


def _product_options(products: list[dict]) -> dict[str, dict | None]:
    options: dict[str, dict | None] = {"Concepto personalizado": None}
    for product in products:
        if product.get("active", True):
            label = f"{product.get('name', 'Producto')} · {product.get('sku') or 'Sin SKU'}"
            options[label] = product
    return options


def _client_options(clients: list[dict]) -> dict[str, str]:
    result = {"Sin cliente": ""}
    for client in clients:
        result[f"{client.get('name', 'Cliente')} · {client.get('client_id', '')}"] = str(client.get("client_id", ""))
    return result


def _quote_total(items: list[dict], discount: float) -> float:
    subtotal = sum(float(item["quantity"]) * float(item["unit_price"]) for item in items)
    return max(subtotal - discount, 0.0)


def render_process_quotes() -> None:
    with st.container(border=True):
        render_page_header(
            "Cotizaciones",
            "Cotiza productos o trabajos y detecta automáticamente qué activos intervienen según sus procesos.",
        )
        st.caption("Los activos se configuran una vez en Activos; aquí solo indicas el producto o los procesos del trabajo.")

    clients = _rows("customers_registry")
    products = _rows("products_registry")
    quotes = _rows("quotes_registry")
    assets = _get_assets()
    client_options = _client_options(clients)
    product_options = _product_options(products)
    process_codes = [code for code, _label in PROCESS_OPTIONS]
    process_labels_map = dict(PROCESS_OPTIONS)

    if not assets:
        st.warning("No hay activos registrados. Puedes cotizar, pero el costo de equipos será cero hasta registrar los equipos.")

    with st.form("process_quote_form", clear_on_submit=True):
        header = st.columns(2)
        with header[0]:
            selected_client = st.selectbox("Cliente", tuple(client_options))
        with header[1]:
            validity_days = st.number_input("Vigencia en días", min_value=1, value=7, step=1)

        st.markdown("#### Conceptos")
        quote_items: list[dict] = []
        for index in range(1, 4):
            st.markdown(f"**Concepto {index}**")
            selected_label = st.selectbox(
                f"Producto o servicio {index}",
                tuple(product_options),
                key=f"process_quote_product_{index}",
            )
            product = product_options[selected_label]
            default_description = str(product.get("name", "")) if product else ""
            default_price = float(product.get("sale_price", 0.0)) if product else 0.0
            default_processes = normalize_process_codes(product.get("process_codes", ())) if product else ()

            first = st.columns([3, 1, 1])
            with first[0]:
                description = st.text_input(
                    f"Descripción {index}", value=default_description,
                    key=f"process_quote_description_{index}", max_chars=140,
                )
            with first[1]:
                quantity = st.number_input(
                    f"Cantidad {index}", min_value=0.0, value=0.0, step=1.0,
                    key=f"process_quote_quantity_{index}",
                )
            with first[2]:
                unit_price = st.number_input(
                    f"Precio unitario {index}", min_value=0.0, value=default_price, step=0.5,
                    key=f"process_quote_price_{index}",
                )

            selected_processes = st.multiselect(
                f"Procesos requeridos {index}",
                options=process_codes,
                default=list(default_processes),
                format_func=lambda code: process_labels_map[code],
                key=f"process_quote_processes_{index}",
                help="Para productos del catálogo se cargan automáticamente; para trabajos personalizados los eliges aquí.",
            )
            normalized = normalize_process_codes(selected_processes)
            detected_assets = assets_for_processes(assets, normalized)
            equipment_cost = equipment_cost_for_processes(assets, normalized)
            _covered, missing = process_coverage(assets, normalized)

            if normalized:
                st.caption(
                    "Activos detectados: "
                    + (", ".join(asset.name for asset in detected_assets) or "ninguno")
                    + f" · Depreciación de equipos por unidad: $ {equipment_cost:,.4f}"
                )
            if missing:
                st.warning(
                    "Sin activo disponible para: "
                    + ", ".join(process_labels_map[code] for code in sorted(missing))
                )

            if description.strip() and quantity > 0 and unit_price > 0:
                quote_items.append(
                    {
                        "product_id": str(product.get("product_id", "")) if product else "",
                        "description": description.strip(),
                        "quantity": float(quantity),
                        "unit_price": float(unit_price),
                        "process_codes": list(normalized),
                        "asset_ids": [asset.asset_id for asset in detected_assets],
                        "asset_names": [asset.name for asset in detected_assets],
                        "equipment_cost_per_unit": equipment_cost,
                        "missing_process_codes": sorted(missing),
                    }
                )

        footer = st.columns(2)
        with footer[0]:
            discount = st.number_input("Descuento total", min_value=0.0, value=0.0, step=0.5)
        with footer[1]:
            notes = st.text_area("Condiciones o notas", max_chars=400)

        submitted = st.form_submit_button("Guardar cotización", type="primary", use_container_width=True)

    if submitted:
        total = _quote_total(quote_items, float(discount))
        missing_items = [item for item in quote_items if item.get("missing_process_codes")]
        if not quote_items:
            st.error("Agrega al menos un concepto completo.")
        elif missing_items:
            st.error("No se puede guardar: uno o más conceptos requieren procesos sin un activo disponible.")
        elif total <= 0:
            st.error("El total debe ser mayor que cero.")
        else:
            quotes.append(
                {
                    "quote_id": uuid4().hex[:10],
                    "created_at_utc": _now(),
                    "client_id": client_options[selected_client],
                    "validity_days": int(validity_days),
                    "items": quote_items,
                    "discount": float(discount),
                    "notes": notes.strip(),
                    "status": "Borrador",
                    "converted_sale_id": "",
                }
            )
            _save("quotes_registry", quotes)
            st.success("Cotización guardada con trazabilidad de procesos y activos.")
            st.rerun()

    st.divider()
    st.subheader("Cotizaciones registradas")
    if not quotes:
        st.info("Todavía no hay cotizaciones.")
        return

    for quote in reversed(quotes):
        items = [dict(item) for item in quote.get("items", []) if isinstance(item, dict)]
        total = _quote_total(items, float(quote.get("discount", 0.0)))
        with st.container(border=True):
            st.markdown(f"### Cotización {quote.get('quote_id', '')}")
            metrics = st.columns(3)
            metrics[0].metric("Conceptos", str(len(items)))
            metrics[1].metric("Total", format_money(total))
            metrics[2].metric("Estado", str(quote.get("status", "Borrador")))
            for item in items:
                st.markdown(f"**{item.get('description', '')}**")
                st.write(
                    f"{float(item.get('quantity', 0.0)):,.2f} × {format_money(float(item.get('unit_price', 0.0)))}"
                )
                st.caption(
                    "Procesos: " + (" · ".join(process_labels(item.get("process_codes", ()))) or "No registrados")
                    + " | Activos: " + (" · ".join(item.get("asset_names", [])) or "No registrados")
                    + f" | Equipos/unidad: $ {float(item.get('equipment_cost_per_unit', 0.0)):,.4f}"
                )
