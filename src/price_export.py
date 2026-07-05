"""Exportación temporal de la lista de precios de CopyMary ERP."""

import csv
from io import StringIO

import streamlit as st

from src.components import render_info_card, render_page_header


def _get_saved_prices() -> list[dict]:
    raw_prices = st.session_state.get("saved_prices", [])
    prices: list[dict] = []
    for raw_price in raw_prices:
        if isinstance(raw_price, dict):
            prices.append(raw_price)
        else:
            prices.append(
                {
                    "price_id": getattr(raw_price, "price_id", ""),
                    "name": getattr(raw_price, "name", "Producto o servicio"),
                    "material_label": getattr(raw_price, "material_label", "Costo manual"),
                    "asset_label": getattr(raw_price, "asset_label", "Sin equipo registrado"),
                    "currency": getattr(raw_price, "currency", "USD"),
                    "profit_margin": float(getattr(raw_price, "profit_margin", 0.0)),
                    "unit_cost": float(getattr(raw_price, "unit_cost", 0.0)),
                    "unit_price": float(getattr(raw_price, "unit_price", 0.0)),
                }
            )
    return prices


def _build_csv(prices: list[dict]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(
        [
            "ID",
            "Producto o servicio",
            "Material",
            "Equipo",
            "Moneda",
            "Margen (%)",
            "Costo unitario",
            "Precio de venta",
        ]
    )
    for price in prices:
        writer.writerow(
            [
                price.get("price_id", ""),
                price.get("name", ""),
                price.get("material_label", ""),
                price.get("asset_label", ""),
                price.get("currency", "USD"),
                f"{float(price.get('profit_margin', 0.0)):.2f}",
                f"{float(price.get('unit_cost', 0.0)):.4f}",
                f"{float(price.get('unit_price', 0.0)):.4f}",
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def render_price_export() -> None:
    """Renderiza la consulta y descarga de la lista temporal de precios."""
    with st.container(border=True):
        render_page_header(
            "Exportar precios",
            "Descarga en CSV los precios guardados durante la sesión para abrirlos en Excel.",
        )
        st.caption("La exportación incluye únicamente los precios que continúan disponibles en esta sesión.")

    prices = _get_saved_prices()
    if not prices:
        st.info("Todavía no hay precios guardados. Primero calcula y guarda precios desde el módulo Costeo.")
        return

    currencies = sorted({str(price.get("currency", "USD")) for price in prices})
    summary_columns = st.columns(3)
    summary_columns[0].metric("Precios disponibles", str(len(prices)))
    summary_columns[1].metric("Monedas presentes", str(len(currencies)))
    summary_columns[2].metric("Formato", "CSV para Excel")

    st.download_button(
        "Descargar lista de precios",
        data=_build_csv(prices),
        file_name="copymary_lista_precios.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )

    st.subheader("Vista previa")
    for price in prices:
        with st.container(border=True):
            st.markdown(f"### {price.get('name', 'Producto o servicio')}")
            st.caption(
                f"ID {price.get('price_id', '')} · {price.get('currency', 'USD')} · "
                f"Margen {float(price.get('profit_margin', 0.0)):.0f}%"
            )
            value_columns = st.columns(2)
            value_columns[0].metric(
                "Costo unitario",
                f"{float(price.get('unit_cost', 0.0)):,.2f}",
            )
            value_columns[1].metric(
                "Precio de venta",
                f"{float(price.get('unit_price', 0.0)):,.2f}",
            )
            render_info_card(
                "Referencia",
                (
                    f"Material: {price.get('material_label', 'Costo manual')}. "
                    f"Equipo: {price.get('asset_label', 'Sin equipo registrado')}."
                ),
                "DATOS EXPORTABLES",
            )

    st.warning(
        "La descarga no reemplaza el almacenamiento permanente. Si la sesión termina antes de descargar, la lista puede perderse."
    )
