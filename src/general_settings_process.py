"""Configuración general sin selección manual repetida de activos."""

from dataclasses import dataclass

import streamlit as st

from src.assets import _get_assets
from src.components import render_info_card, render_page_header
from src.production_processes import (
    PROCESS_OPTIONS,
    assets_for_processes,
    equipment_cost_for_processes,
    normalize_process_codes,
    process_coverage,
)


@dataclass(frozen=True)
class GeneralSettings:
    business_name: str
    currency: str
    profit_margin: float
    margin_method: str
    monthly_internet: float
    monthly_electricity: float
    estimated_monthly_units: int

    @property
    def monthly_fixed_costs(self) -> float:
        return self.monthly_internet + self.monthly_electricity

    @property
    def fixed_cost_per_unit(self) -> float:
        return self.monthly_fixed_costs / max(self.estimated_monthly_units, 1)

    @property
    def sale_multiplier(self) -> float:
        if self.margin_method == "Margen sobre venta":
            return 1 / max(1 - (self.profit_margin / 100), 0.01)
        return 1 + (self.profit_margin / 100)


def _money(value: float, currency: str) -> str:
    symbol = {"USD": "$", "VES": "Bs", "EUR": "€"}.get(currency, currency)
    return f"{symbol} {value:,.2f}"


def _defaults() -> GeneralSettings:
    stored = st.session_state.get("general_settings")
    return GeneralSettings(
        business_name=str(getattr(stored, "business_name", "Copy Mary")),
        currency=str(getattr(stored, "currency", "USD")),
        profit_margin=float(getattr(stored, "profit_margin", 40.0)),
        margin_method=str(getattr(stored, "margin_method", "Margen sobre venta")),
        monthly_internet=float(getattr(stored, "monthly_internet", 5.0)),
        monthly_electricity=float(getattr(stored, "monthly_electricity", 3.0)),
        estimated_monthly_units=int(getattr(stored, "estimated_monthly_units", 200)),
    )


def render_general_settings_process() -> None:
    with st.container(border=True):
        render_page_header(
            "Configuración General",
            "Define únicamente parámetros globales. Los activos usados se detectan al cotizar según los procesos.",
        )
        st.caption("No necesitas volver aquí cuando compres, reemplaces o desactives una máquina.")

    defaults = _defaults()
    with st.form("general_settings_process_form"):
        business_name = st.text_input("Nombre del negocio", value=defaults.business_name, max_chars=80)
        currency = st.selectbox(
            "Moneda principal", ("USD", "VES", "EUR"),
            index=("USD", "VES", "EUR").index(defaults.currency) if defaults.currency in ("USD", "VES", "EUR") else 0,
        )
        margin_columns = st.columns(2)
        with margin_columns[0]:
            profit_margin = st.number_input(
                "Margen objetivo (%)", min_value=0.0, max_value=95.0,
                value=float(defaults.profit_margin), step=1.0,
            )
        with margin_columns[1]:
            methods = ("Margen sobre venta", "Recargo sobre costo")
            margin_method = st.selectbox(
                "Método", methods,
                index=methods.index(defaults.margin_method) if defaults.margin_method in methods else 0,
            )

        cost_columns = st.columns(3)
        with cost_columns[0]:
            monthly_internet = st.number_input(
                "Internet imputado al negocio", min_value=0.0,
                value=float(defaults.monthly_internet), step=1.0,
            )
        with cost_columns[1]:
            monthly_electricity = st.number_input(
                "Electricidad imputada al negocio", min_value=0.0,
                value=float(defaults.monthly_electricity), step=1.0,
            )
        with cost_columns[2]:
            estimated_monthly_units = st.number_input(
                "Unidades productivas equivalentes al mes", min_value=1,
                value=int(defaults.estimated_monthly_units), step=1,
            )

        submitted = st.form_submit_button("Guardar configuración", type="primary", use_container_width=True)

    if submitted:
        if not business_name.strip():
            st.error("El nombre del negocio no puede quedar vacío.")
        else:
            st.session_state.general_settings = GeneralSettings(
                business_name=business_name.strip(), currency=currency,
                profit_margin=float(profit_margin), margin_method=margin_method,
                monthly_internet=float(monthly_internet),
                monthly_electricity=float(monthly_electricity),
                estimated_monthly_units=int(estimated_monthly_units),
            )
            st.success("Configuración global guardada.")
            st.rerun()

    settings = st.session_state.get("general_settings", defaults)
    st.divider()
    summary = st.columns(4)
    summary[0].metric("Negocio", settings.business_name)
    summary[1].metric("Costo fijo por unidad", _money(settings.fixed_cost_per_unit, settings.currency))
    summary[2].metric("Margen objetivo", f"{settings.profit_margin:.1f}%")
    summary[3].metric("Factor de venta", f"× {settings.sale_multiplier:.4f}")

    assets = _get_assets()
    available_assets = [asset for asset in assets if asset.available_for_quoting]
    render_info_card(
        "Activos administrados automáticamente",
        (
            f"Hay {len(available_assets)} equipo(s) activo(s) habilitado(s) para cotizaciones. "
            "El costo de cada trabajo se determina por sus procesos; no existe una selección global de equipos."
        ),
        "ORIGEN: ACTIVOS",
    )

    st.divider()
    st.subheader("Comprobador de procesos y equipos")
    st.caption("Esta herramienta es solo de consulta; no guarda una selección global.")
    process_map = dict(PROCESS_OPTIONS)
    selected_processes = st.multiselect(
        "Procesos de un trabajo de ejemplo",
        options=[code for code, _label in PROCESS_OPTIONS],
        format_func=lambda code: process_map[code],
    )
    normalized = normalize_process_codes(selected_processes)
    detected = assets_for_processes(assets, normalized)
    equipment_cost = equipment_cost_for_processes(assets, normalized)
    _covered, missing = process_coverage(assets, normalized)

    cols = st.columns(3)
    cols[0].metric("Procesos", str(len(normalized)))
    cols[1].metric("Equipos detectados", str(len(detected)))
    cols[2].metric("Depreciación/unidad", f"$ {equipment_cost:,.4f}")
    if detected:
        st.success("Equipos: " + " · ".join(asset.name for asset in detected))
    if missing:
        st.error("Faltan activos para: " + " · ".join(process_map[code] for code in sorted(missing)))
    elif normalized:
        st.info("Todos los procesos del ejemplo tienen al menos un activo disponible.")
