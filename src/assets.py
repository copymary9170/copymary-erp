"""Registro temporal de activos productivos de CopyMary ERP."""

from dataclasses import asdict, dataclass, replace
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money
from src.production_processes import PROCESS_OPTIONS, normalize_process_codes, process_labels


ASSET_STATUSES = ("Activo", "En mantenimiento", "Fuera de servicio", "Dado de baja", "Vendido")
ASSET_CATEGORIES = (
    "Impresora",
    "Equipo de corte",
    "Equipo de sublimación",
    "Plastificadora o laminadora",
    "Computación",
    "Otro",
)


@dataclass(frozen=True)
class Asset:
    asset_id: str
    name: str
    category: str
    acquisition_cost: float
    lifetime_units: int
    current_units: int
    status: str = "Activo"
    participates_in_costing: bool = True
    process_codes: tuple[str, ...] = ()

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

    @property
    def available_for_quoting(self) -> bool:
        return self.status == "Activo" and self.participates_in_costing and bool(self.process_codes)


def _asset_from_dict(raw_asset: dict) -> Asset:
    """Mantiene compatibilidad con activos creados antes del costeo por procesos."""
    return Asset(
        asset_id=str(raw_asset.get("asset_id", uuid4().hex[:8])),
        name=str(raw_asset.get("name", "Equipo")),
        category=str(raw_asset.get("category", "Otro")),
        acquisition_cost=float(raw_asset.get("acquisition_cost", 0.0)),
        lifetime_units=max(int(raw_asset.get("lifetime_units", 1)), 1),
        current_units=max(int(raw_asset.get("current_units", 0)), 0),
        status=str(raw_asset.get("status", "Activo")),
        participates_in_costing=bool(raw_asset.get("participates_in_costing", True)),
        process_codes=normalize_process_codes(raw_asset.get("process_codes", ())),
    )


def _get_assets() -> list[Asset]:
    raw_assets = st.session_state.get("assets_registry", [])
    assets: list[Asset] = []
    for raw_asset in raw_assets:
        if isinstance(raw_asset, Asset):
            assets.append(replace(raw_asset, process_codes=normalize_process_codes(raw_asset.process_codes)))
        elif isinstance(raw_asset, dict):
            assets.append(_asset_from_dict(raw_asset))
    return assets


def _save_assets(assets: list[Asset]) -> None:
    st.session_state.assets_registry = [asdict(asset) for asset in assets]


def _replace_asset(assets: list[Asset], updated_asset: Asset) -> list[Asset]:
    return [updated_asset if asset.asset_id == updated_asset.asset_id else asset for asset in assets]


def _update_asset_units(assets: list[Asset], asset_id: str, units_to_add: int) -> list[Asset]:
    updated_assets: list[Asset] = []
    for asset in assets:
        if asset.asset_id == asset_id:
            updated_assets.append(replace(asset, current_units=asset.current_units + units_to_add))
        else:
            updated_assets.append(asset)
    return updated_assets


def render_assets() -> None:
    """Renderiza activos y define en qué procesos se usan para cotizar."""
    with st.container(border=True):
        render_page_header(
            "Activos",
            "Registra equipos, controla su estado y define los procesos donde participan al cotizar.",
        )
        st.caption("Los registros se conservan únicamente durante la sesión actual.")

    st.warning(
        "Este módulo todavía no utiliza base de datos. Los activos pueden perderse al cerrar o reiniciar la aplicación."
    )

    assets = _get_assets()
    process_codes = [code for code, _label in PROCESS_OPTIONS]
    process_label_map = dict(PROCESS_OPTIONS)

    st.subheader("Registrar activo")
    with st.form("asset_form", clear_on_submit=True):
        first_row = st.columns(3)
        with first_row[0]:
            name = st.text_input("Nombre del equipo", max_chars=80)
        with first_row[1]:
            category = st.selectbox("Categoría", ASSET_CATEGORIES)
        with first_row[2]:
            status = st.selectbox("Estado operativo", ASSET_STATUSES)

        second_row = st.columns(3)
        with second_row[0]:
            acquisition_cost = st.number_input(
                "Costo de adquisición", min_value=0.0, value=0.0, step=10.0
            )
        with second_row[1]:
            lifetime_units = st.number_input(
                "Vida útil estimada en unidades", min_value=1, value=30000, step=100
            )
        with second_row[2]:
            current_units = st.number_input(
                "Unidades acumuladas iniciales", min_value=0, value=0, step=100
            )

        participates_in_costing = st.checkbox(
            "Usar este activo para calcular costos y cotizaciones",
            value=True,
            help="Solo se utilizará cuando esté Activo y el producto requiera uno de sus procesos.",
        )
        selected_processes = st.multiselect(
            "Procesos que puede realizar este activo",
            options=process_codes,
            format_func=lambda code: process_label_map[code],
            help="Se configura una sola vez. Las cotizaciones detectarán el equipo según los procesos del producto.",
        )

        submitted = st.form_submit_button(
            "Registrar activo", type="primary", use_container_width=True
        )

    if submitted:
        cleaned_name = name.strip()
        if not cleaned_name:
            st.error("El nombre del equipo no puede quedar vacío.")
        elif acquisition_cost <= 0:
            st.error("El costo de adquisición debe ser mayor que cero.")
        elif participates_in_costing and not selected_processes:
            st.error("Selecciona al menos un proceso o desactiva su uso en costos y cotizaciones.")
        else:
            assets.append(
                Asset(
                    asset_id=uuid4().hex[:8],
                    name=cleaned_name,
                    category=category,
                    acquisition_cost=float(acquisition_cost),
                    lifetime_units=int(lifetime_units),
                    current_units=int(current_units),
                    status=status,
                    participates_in_costing=bool(participates_in_costing),
                    process_codes=normalize_process_codes(selected_processes),
                )
            )
            _save_assets(assets)
            st.success("Activo registrado y disponible para los procesos seleccionados.")
            st.rerun()

    st.divider()
    st.subheader("Resumen de activos")

    total_cost = sum(asset.acquisition_cost for asset in assets)
    total_remaining = sum(asset.remaining_value for asset in assets)
    available_count = sum(1 for asset in assets if asset.available_for_quoting)
    summary_columns = st.columns(4)
    summary_columns[0].metric("Activos registrados", str(len(assets)))
    summary_columns[1].metric("Disponibles para cotizar", str(available_count))
    summary_columns[2].metric("Inversión registrada", format_money(total_cost))
    summary_columns[3].metric("Valor pendiente", format_money(total_remaining))

    if not assets:
        st.info("Todavía no hay activos registrados en esta sesión.")
        return

    st.subheader("Equipos registrados")
    for asset in assets:
        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {asset.name}")
                state_text = "Disponible para cotizar" if asset.available_for_quoting else "No usado automáticamente"
                st.caption(f"{asset.category} · {asset.status} · {state_text} · ID {asset.asset_id}")
            with title_columns[1]:
                if st.button("Eliminar", key=f"delete_asset_{asset.asset_id}", use_container_width=True):
                    _save_assets([item for item in assets if item.asset_id != asset.asset_id])
                    st.rerun()

            metric_columns = st.columns(5)
            metric_columns[0].metric("Costo", format_money(asset.acquisition_cost))
            metric_columns[1].metric("Depreciación/unidad", f"$ {asset.depreciation_per_unit:,.4f}")
            metric_columns[2].metric("Unidades acumuladas", f"{asset.current_units:,}")
            metric_columns[3].metric("Uso estimado", f"{asset.usage_percent:.1f}%")
            metric_columns[4].metric("Valor pendiente", format_money(asset.remaining_value))
            st.progress(asset.usage_percent / 100)

            labels = process_labels(asset.process_codes)
            st.markdown("**Procesos para cotización:** " + (" · ".join(labels) if labels else "Ninguno"))

            with st.expander("Editar estado y procesos", expanded=not asset.process_codes):
                with st.form(f"asset_process_form_{asset.asset_id}"):
                    edit_columns = st.columns(2)
                    with edit_columns[0]:
                        edited_status = st.selectbox(
                            "Estado operativo",
                            ASSET_STATUSES,
                            index=ASSET_STATUSES.index(asset.status) if asset.status in ASSET_STATUSES else 0,
                            key=f"status_{asset.asset_id}",
                        )
                        edited_participation = st.checkbox(
                            "Usar para costos y cotizaciones",
                            value=asset.participates_in_costing,
                            key=f"participation_{asset.asset_id}",
                        )
                    with edit_columns[1]:
                        edited_processes = st.multiselect(
                            "Procesos que realiza",
                            options=process_codes,
                            default=list(asset.process_codes),
                            format_func=lambda code: process_label_map[code],
                            key=f"processes_{asset.asset_id}",
                        )
                    save_processes = st.form_submit_button(
                        "Guardar estado y procesos", type="primary", use_container_width=True
                    )
                if save_processes:
                    if edited_participation and not edited_processes:
                        st.error("Selecciona al menos un proceso para usar el activo en cotizaciones.")
                    else:
                        updated_asset = replace(
                            asset,
                            status=edited_status,
                            participates_in_costing=bool(edited_participation),
                            process_codes=normalize_process_codes(edited_processes),
                        )
                        _save_assets(_replace_asset(assets, updated_asset))
                        st.success("Estado y procesos actualizados.")
                        st.rerun()

            with st.form(f"asset_usage_form_{asset.asset_id}", clear_on_submit=True):
                usage_columns = st.columns([2, 1])
                with usage_columns[0]:
                    units_to_add = st.number_input(
                        "Agregar unidades producidas",
                        min_value=1,
                        value=1,
                        step=1,
                        key=f"units_to_add_{asset.asset_id}",
                    )
                with usage_columns[1]:
                    update_submitted = st.form_submit_button(
                        "Actualizar uso", type="primary", use_container_width=True
                    )

            if update_submitted:
                _save_assets(_update_asset_units(assets, asset.asset_id, int(units_to_add)))
                st.success(f"Se agregaron {int(units_to_add):,} unidades a {asset.name}.")
                st.rerun()

            detail_columns = st.columns(2)
            with detail_columns[0]:
                render_info_card(
                    "Depreciación acumulada",
                    f"El equipo ha consumido aproximadamente {format_money(asset.accumulated_depreciation)} de su valor.",
                    "SEGUIMIENTO DE USO",
                )
            with detail_columns[1]:
                render_info_card(
                    "Uso automático al cotizar",
                    (
                        "El ERP lo añadirá cuando un producto requiera alguno de sus procesos."
                        if asset.available_for_quoting
                        else "No se añadirá hasta que esté Activo, habilitado y tenga procesos asignados."
                    ),
                    "COSTEO POR PROCESOS",
                )
