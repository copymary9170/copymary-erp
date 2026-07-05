"""Registro temporal de activos productivos de CopyMary ERP."""

from dataclasses import asdict, dataclass, replace
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header


@dataclass(frozen=True)
class Asset:
    asset_id: str
    name: str
    category: str
    acquisition_cost: float
    lifetime_units: int
    current_units: int

    @property
    def depreciation_per_unit(self) -> float:
        return self.acquisition_cost / self.lifetime_units

    @property
    def accumulated_depreciation(self) -> float:
        used_units = min(self.current_units, self.lifetime_units)
        return used_units * self.depreciation_per_unit

    @property
    def remaining_value(self) -> float:
        return max(self.acquisition_cost - self.accumulated_depreciation, 0.0)

    @property
    def usage_percent(self) -> float:
        return min((self.current_units / self.lifetime_units) * 100, 100.0)


CURRENCY_SYMBOL = "$"


def _format_money(value: float) -> str:
    return f"{CURRENCY_SYMBOL} {value:,.2f}"


def _get_assets() -> list[Asset]:
    raw_assets = st.session_state.get("assets_registry", [])
    assets: list[Asset] = []
    for raw_asset in raw_assets:
        if isinstance(raw_asset, Asset):
            assets.append(raw_asset)
        elif isinstance(raw_asset, dict):
            assets.append(Asset(**raw_asset))
    return assets


def _save_assets(assets: list[Asset]) -> None:
    st.session_state.assets_registry = [asdict(asset) for asset in assets]


def _update_asset_units(assets: list[Asset], asset_id: str, units_to_add: int) -> list[Asset]:
    updated_assets: list[Asset] = []
    for asset in assets:
        if asset.asset_id == asset_id:
            updated_assets.append(
                replace(asset, current_units=asset.current_units + units_to_add)
            )
        else:
            updated_assets.append(asset)
    return updated_assets


def render_assets() -> None:
    """Renderiza el registro temporal de activos productivos."""
    with st.container(border=True):
        render_page_header(
            "Activos",
            "Registra máquinas y actualiza su uso para estimar depreciación y reposición.",
        )
        st.caption("Los registros se conservan únicamente durante la sesión actual.")

    st.warning(
        "Este módulo todavía no utiliza base de datos. Los activos pueden perderse al cerrar o reiniciar la aplicación."
    )

    assets = _get_assets()

    st.subheader("Registrar activo")
    with st.form("asset_form", clear_on_submit=True):
        first_row = st.columns(2)
        with first_row[0]:
            name = st.text_input("Nombre del equipo", max_chars=80)
        with first_row[1]:
            category = st.selectbox(
                "Categoría",
                ("Impresora", "Equipo de corte", "Equipo de sublimación", "Computación", "Otro"),
            )

        second_row = st.columns(3)
        with second_row[0]:
            acquisition_cost = st.number_input(
                "Costo de adquisición",
                min_value=0.0,
                value=0.0,
                step=10.0,
            )
        with second_row[1]:
            lifetime_units = st.number_input(
                "Vida útil estimada en unidades",
                min_value=1,
                value=30000,
                step=100,
            )
        with second_row[2]:
            current_units = st.number_input(
                "Unidades acumuladas iniciales",
                min_value=0,
                value=0,
                step=100,
            )

        submitted = st.form_submit_button(
            "Registrar activo",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        cleaned_name = name.strip()
        if not cleaned_name:
            st.error("El nombre del equipo no puede quedar vacío.")
        elif acquisition_cost <= 0:
            st.error("El costo de adquisición debe ser mayor que cero.")
        else:
            assets.append(
                Asset(
                    asset_id=uuid4().hex[:8],
                    name=cleaned_name,
                    category=category,
                    acquisition_cost=float(acquisition_cost),
                    lifetime_units=int(lifetime_units),
                    current_units=int(current_units),
                )
            )
            _save_assets(assets)
            st.success("Activo registrado durante esta sesión.")
            st.rerun()

    st.divider()
    st.subheader("Resumen de activos")

    total_cost = sum(asset.acquisition_cost for asset in assets)
    total_remaining = sum(asset.remaining_value for asset in assets)
    total_units = sum(asset.current_units for asset in assets)
    summary_columns = st.columns(4)
    summary_columns[0].metric("Activos registrados", str(len(assets)))
    summary_columns[1].metric("Inversión registrada", _format_money(total_cost))
    summary_columns[2].metric("Valor pendiente", _format_money(total_remaining))
    summary_columns[3].metric("Unidades acumuladas", f"{total_units:,}")

    if not assets:
        st.info("Todavía no hay activos registrados en esta sesión.")
        return

    st.subheader("Equipos registrados")
    for asset in assets:
        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {asset.name}")
                st.caption(f"{asset.category} · ID {asset.asset_id}")
            with title_columns[1]:
                if st.button("Eliminar", key=f"delete_asset_{asset.asset_id}", use_container_width=True):
                    _save_assets([item for item in assets if item.asset_id != asset.asset_id])
                    st.rerun()

            metric_columns = st.columns(5)
            metric_columns[0].metric("Costo", _format_money(asset.acquisition_cost))
            metric_columns[1].metric("Depreciación/unidad", _format_money(asset.depreciation_per_unit))
            metric_columns[2].metric("Unidades acumuladas", f"{asset.current_units:,}")
            metric_columns[3].metric("Uso estimado", f"{asset.usage_percent:.1f}%")
            metric_columns[4].metric("Valor pendiente", _format_money(asset.remaining_value))

            st.progress(asset.usage_percent / 100)

            with st.form(f"asset_usage_form_{asset.asset_id}", clear_on_submit=True):
                usage_columns = st.columns([2, 1])
                with usage_columns[0]:
                    units_to_add = st.number_input(
                        "Agregar unidades producidas",
                        min_value=1,
                        value=1,
                        step=1,
                        key=f"units_to_add_{asset.asset_id}",
                        help="Suma nuevas unidades al contador acumulado del equipo.",
                    )
                with usage_columns[1]:
                    update_submitted = st.form_submit_button(
                        "Actualizar uso",
                        type="primary",
                        use_container_width=True,
                    )

            if update_submitted:
                _save_assets(
                    _update_asset_units(
                        assets,
                        asset_id=asset.asset_id,
                        units_to_add=int(units_to_add),
                    )
                )
                st.success(f"Se agregaron {int(units_to_add):,} unidades a {asset.name}.")
                st.rerun()

            detail_columns = st.columns(2)
            with detail_columns[0]:
                render_info_card(
                    "Depreciación acumulada",
                    (
                        f"Según las unidades registradas, este equipo ha consumido aproximadamente "
                        f"{_format_money(asset.accumulated_depreciation)} de su valor."
                    ),
                    "SEGUIMIENTO DE USO",
                )
            with detail_columns[1]:
                render_info_card(
                    "Reserva sugerida",
                    (
                        f"Para financiar el reemplazo futuro de este equipo, reserva aproximadamente "
                        f"{_format_money(asset.depreciation_per_unit)} por cada unidad producida."
                    ),
                    "DEPRECIACIÓN ORIENTATIVA",
                )
