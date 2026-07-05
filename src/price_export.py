"""Importación y exportación temporal de la lista de precios de CopyMary ERP."""

import csv
from io import StringIO
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header


CSV_HEADERS = [
    "ID",
    "Producto o servicio",
    "Material",
    "Equipo",
    "Moneda",
    "Margen (%)",
    "Costo unitario",
    "Precio de venta",
]


def _get_saved_prices() -> list[dict]:
    raw_prices = st.session_state.get("saved_prices", [])
    prices: list[dict] = []
    for raw_price in raw_prices:
        if isinstance(raw_price, dict):
            prices.append(dict(raw_price))
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
    writer.writerow(CSV_HEADERS)
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


def _parse_number(value: str, field_name: str, row_number: int) -> float:
    cleaned_value = value.strip().replace(",", ".")
    try:
        number = float(cleaned_value)
    except ValueError as exc:
        raise ValueError(
            f"Fila {row_number}: el campo '{field_name}' debe contener un número válido."
        ) from exc
    if number < 0:
        raise ValueError(
            f"Fila {row_number}: el campo '{field_name}' no puede ser negativo."
        )
    return number


def _parse_csv(file_bytes: bytes) -> list[dict]:
    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("El archivo debe estar guardado con codificación UTF-8.") from exc

    reader = csv.DictReader(StringIO(decoded), delimiter=";")
    if reader.fieldnames != CSV_HEADERS:
        raise ValueError(
            "El archivo no tiene las columnas esperadas. Usa un CSV exportado desde CopyMary ERP."
        )

    imported_prices: list[dict] = []
    for row_number, row in enumerate(reader, start=2):
        name = (row.get("Producto o servicio") or "").strip()
        if not name:
            raise ValueError(f"Fila {row_number}: falta el nombre del producto o servicio.")

        currency = (row.get("Moneda") or "USD").strip().upper()
        if currency not in {"USD", "VES", "EUR"}:
            raise ValueError(
                f"Fila {row_number}: la moneda debe ser USD, VES o EUR."
            )

        imported_prices.append(
            {
                "price_id": (row.get("ID") or "").strip() or uuid4().hex[:8],
                "name": name,
                "material_label": (row.get("Material") or "Costo manual").strip()
                or "Costo manual",
                "asset_label": (row.get("Equipo") or "Sin equipo registrado").strip()
                or "Sin equipo registrado",
                "currency": currency,
                "profit_margin": _parse_number(
                    row.get("Margen (%)") or "0",
                    "Margen (%)",
                    row_number,
                ),
                "unit_cost": _parse_number(
                    row.get("Costo unitario") or "0",
                    "Costo unitario",
                    row_number,
                ),
                "unit_price": _parse_number(
                    row.get("Precio de venta") or "0",
                    "Precio de venta",
                    row_number,
                ),
            }
        )

    if not imported_prices:
        raise ValueError("El archivo no contiene precios para importar.")
    return imported_prices


def _merge_prices(current_prices: list[dict], imported_prices: list[dict]) -> list[dict]:
    merged_by_id = {
        str(price.get("price_id", "")): dict(price)
        for price in current_prices
        if price.get("price_id")
    }
    for price in imported_prices:
        merged_by_id[str(price["price_id"])] = dict(price)
    return list(merged_by_id.values())


def render_price_export() -> None:
    """Renderiza la importación, consulta y descarga de precios temporales."""
    with st.container(border=True):
        render_page_header(
            "Importar y exportar precios",
            "Recupera una lista CSV o descarga los precios guardados durante la sesión.",
        )
        st.caption(
            "La información continúa siendo temporal: importa al comenzar y exporta antes de cerrar."
        )

    st.subheader("Importar lista de precios")
    uploaded_file = st.file_uploader(
        "Selecciona un archivo CSV exportado desde CopyMary ERP",
        type=("csv",),
        accept_multiple_files=False,
    )
    import_mode = st.radio(
        "Cómo aplicar la importación",
        ("Reemplazar la lista actual", "Combinar por ID"),
        horizontal=True,
        help="Combinar conserva los precios actuales y reemplaza solo los que tengan el mismo ID.",
    )

    if uploaded_file is not None and st.button(
        "Importar precios",
        type="primary",
        use_container_width=True,
    ):
        try:
            imported_prices = _parse_csv(uploaded_file.getvalue())
        except ValueError as exc:
            st.error(str(exc))
        else:
            current_prices = _get_saved_prices()
            if import_mode == "Combinar por ID":
                st.session_state.saved_prices = _merge_prices(
                    current_prices,
                    imported_prices,
                )
            else:
                st.session_state.saved_prices = imported_prices
            st.success(f"Se importaron {len(imported_prices)} precio(s) correctamente.")
            st.rerun()

    st.divider()
    prices = _get_saved_prices()
    st.subheader("Exportar lista de precios")
    if not prices:
        st.info(
            "Todavía no hay precios disponibles. Puedes importarlos aquí o guardarlos desde Costeo."
        )
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
                "DATOS IMPORTABLES Y EXPORTABLES",
            )

    st.warning(
        "La importación y la descarga no reemplazan una base de datos. La lista puede perderse al terminar la sesión."
    )
