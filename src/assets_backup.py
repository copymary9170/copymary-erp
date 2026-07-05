"""Respaldo CSV temporal para los activos de CopyMary ERP."""

import csv
from io import StringIO
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header


CSV_HEADERS = [
    "ID",
    "Nombre",
    "Categoría",
    "Costo de adquisición",
    "Vida útil en unidades",
    "Unidades acumuladas",
]


def _get_assets() -> list[dict]:
    assets: list[dict] = []
    for raw_asset in st.session_state.get("assets_registry", []):
        if isinstance(raw_asset, dict):
            assets.append(dict(raw_asset))
        else:
            assets.append(
                {
                    "asset_id": getattr(raw_asset, "asset_id", ""),
                    "name": getattr(raw_asset, "name", "Equipo"),
                    "category": getattr(raw_asset, "category", "Otro"),
                    "acquisition_cost": float(getattr(raw_asset, "acquisition_cost", 0.0)),
                    "lifetime_units": int(getattr(raw_asset, "lifetime_units", 1)),
                    "current_units": int(getattr(raw_asset, "current_units", 0)),
                }
            )
    return assets


def _build_csv(assets: list[dict]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(CSV_HEADERS)
    for asset in assets:
        writer.writerow(
            [
                asset.get("asset_id", ""),
                asset.get("name", ""),
                asset.get("category", ""),
                f"{float(asset.get('acquisition_cost', 0.0)):.4f}",
                int(asset.get("lifetime_units", 1)),
                int(asset.get("current_units", 0)),
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _parse_float(value: str, field: str, row_number: int) -> float:
    try:
        number = float(value.strip().replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"Fila {row_number}: '{field}' debe ser numérico.") from exc
    if number <= 0:
        raise ValueError(f"Fila {row_number}: '{field}' debe ser mayor que cero.")
    return number


def _parse_int(value: str, field: str, row_number: int, allow_zero: bool) -> int:
    try:
        number = int(value.strip())
    except ValueError as exc:
        raise ValueError(f"Fila {row_number}: '{field}' debe ser un entero.") from exc
    minimum = 0 if allow_zero else 1
    if number < minimum:
        raise ValueError(f"Fila {row_number}: '{field}' debe ser igual o mayor que {minimum}.")
    return number


def _parse_csv(file_bytes: bytes) -> list[dict]:
    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("El archivo debe usar codificación UTF-8.") from exc

    reader = csv.DictReader(StringIO(decoded), delimiter=";")
    if reader.fieldnames != CSV_HEADERS:
        raise ValueError("El CSV no tiene la estructura esperada para Activos.")

    assets: list[dict] = []
    for row_number, row in enumerate(reader, start=2):
        name = (row.get("Nombre") or "").strip()
        category = (row.get("Categoría") or "").strip()
        if not name or not category:
            raise ValueError(f"Fila {row_number}: nombre y categoría son obligatorios.")

        assets.append(
            {
                "asset_id": (row.get("ID") or "").strip() or uuid4().hex[:8],
                "name": name,
                "category": category,
                "acquisition_cost": _parse_float(
                    row.get("Costo de adquisición") or "0",
                    "Costo de adquisición",
                    row_number,
                ),
                "lifetime_units": _parse_int(
                    row.get("Vida útil en unidades") or "0",
                    "Vida útil en unidades",
                    row_number,
                    allow_zero=False,
                ),
                "current_units": _parse_int(
                    row.get("Unidades acumuladas") or "0",
                    "Unidades acumuladas",
                    row_number,
                    allow_zero=True,
                ),
            }
        )

    if not assets:
        raise ValueError("El archivo no contiene activos.")
    return assets


def _merge_assets(current: list[dict], imported: list[dict]) -> list[dict]:
    merged = {str(asset.get("asset_id", "")): asset for asset in current}
    for asset in imported:
        merged[str(asset["asset_id"])] = asset
    return list(merged.values())


def render_assets_backup() -> None:
    """Renderiza importación y exportación manual de activos."""
    with st.container(border=True):
        render_page_header(
            "Respaldar activos",
            "Exporta o recupera máquinas y unidades acumuladas mediante CSV.",
        )
        st.caption("El respaldo es manual y los datos siguen siendo temporales.")

    current_assets = _get_assets()
    uploaded_file = st.file_uploader(
        "Selecciona un CSV de activos",
        type=("csv",),
        accept_multiple_files=False,
    )
    mode = st.radio(
        "Cómo importar",
        ("Reemplazar activos actuales", "Combinar por ID"),
        horizontal=True,
    )

    if uploaded_file is not None and st.button(
        "Importar activos",
        type="primary",
        use_container_width=True,
    ):
        try:
            imported_assets = _parse_csv(uploaded_file.getvalue())
        except ValueError as exc:
            st.error(str(exc))
        else:
            if mode == "Combinar por ID":
                st.session_state.assets_registry = _merge_assets(current_assets, imported_assets)
            else:
                st.session_state.assets_registry = imported_assets
            st.success(f"Se importaron {len(imported_assets)} activo(s).")
            st.rerun()

    st.divider()
    current_assets = _get_assets()
    if not current_assets:
        st.info("No hay activos disponibles para exportar. Regístralos primero en Activos.")
        return

    st.download_button(
        "Descargar activos en CSV",
        data=_build_csv(current_assets),
        file_name="copymary_activos.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )

    summary_columns = st.columns(3)
    summary_columns[0].metric("Activos disponibles", str(len(current_assets)))
    summary_columns[1].metric(
        "Inversión registrada",
        f"$ {sum(float(asset.get('acquisition_cost', 0.0)) for asset in current_assets):,.2f}",
    )
    summary_columns[2].metric(
        "Unidades acumuladas",
        f"{sum(int(asset.get('current_units', 0)) for asset in current_assets):,}",
    )

    render_info_card(
        "Contenido del respaldo",
        "Incluye nombre, categoría, costo, vida útil y unidades acumuladas de cada equipo.",
        "CSV PARA EXCEL",
    )
