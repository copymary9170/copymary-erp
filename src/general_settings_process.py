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
    # Tasas de cambio de referencia (VES por 1 USD) y comisiones/impuestos (%).
    # Ver la nota en render_general_settings_process(): existe otra clase
    # GeneralSettings en src/general_settings.py con estos mismos campos;
    # esta es la que de verdad está activa (process_quote_loader.py la
    # registra por encima), así que es aquí donde tienen que vivir para que
    # se vean en la app.
    bcv_rate: float = 0.0
    binance_rate: float = 0.0
    kontigo_in_rate: float = 0.0
    kontigo_out_rate: float = 0.0
    # Comisión (%) que cobra la propia plataforma Kontigo en cada operación,
    # distinta de la tasa de cambio: la tasa dice cuántos VES equivalen a 1
    # USD; esta comisión es lo que Kontigo se queda del monto de la
    # operación, por separado, tanto al entrar como al salir.
    kontigo_in_fee: float = 0.0
    kontigo_out_fee: float = 0.0
    iva_rate: float = 16.0
    igtf_rate: float = 3.0
    mobile_payment_fee: float = 0.0
    pos_fee: float = 0.0

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

    def rate_for(self, rate_name: str) -> float:
        return {
            "BCV": self.bcv_rate,
            "Binance": self.binance_rate,
            "Kontigo (entrada)": self.kontigo_in_rate,
            "Kontigo (salida)": self.kontigo_out_rate,
        }.get(rate_name, 0.0)

    def fee_for_payment_method(self, payment_method: str) -> float:
        normalized = payment_method.strip().casefold()
        if "kontigo" in normalized and "entrada" in normalized:
            return self.kontigo_in_fee
        if "kontigo" in normalized and "salida" in normalized:
            return self.kontigo_out_fee
        if "móvil" in normalized or "movil" in normalized:
            return self.mobile_payment_fee
        if "punto" in normalized or "tarjeta" in normalized or "pos" in normalized:
            return self.pos_fee
        return 0.0

    def net_after_fees(self, gross_amount: float, payment_method: str, *, apply_igtf: bool = False) -> float:
        fee_rate = self.fee_for_payment_method(payment_method)
        net = gross_amount * (1 - fee_rate / 100)
        if apply_igtf:
            net *= (1 - self.igtf_rate / 100)
        return net


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
        bcv_rate=float(getattr(stored, "bcv_rate", 0.0)),
        binance_rate=float(getattr(stored, "binance_rate", 0.0)),
        kontigo_in_rate=float(getattr(stored, "kontigo_in_rate", 0.0)),
        kontigo_out_rate=float(getattr(stored, "kontigo_out_rate", 0.0)),
        kontigo_in_fee=float(getattr(stored, "kontigo_in_fee", 0.0)),
        kontigo_out_fee=float(getattr(stored, "kontigo_out_fee", 0.0)),
        iva_rate=float(getattr(stored, "iva_rate", 16.0)),
        igtf_rate=float(getattr(stored, "igtf_rate", 3.0)),
        mobile_payment_fee=float(getattr(stored, "mobile_payment_fee", 0.0)),
        pos_fee=float(getattr(stored, "pos_fee", 0.0)),
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

        st.markdown("#### Tasas de cambio de referencia (VES por 1 USD)")
        st.caption("Se guardan por separado porque suelen ser distintas: BCV es la oficial, Binance/paralelo es la de mercado, y Kontigo tiene una tasa cuando el dinero entra y otra cuando sale.")
        rate_columns = st.columns(4)
        with rate_columns[0]:
            bcv_rate = st.number_input("Tasa BCV", min_value=0.0, value=float(defaults.bcv_rate), step=0.01, format="%.4f")
        with rate_columns[1]:
            binance_rate = st.number_input("Tasa Binance / paralelo", min_value=0.0, value=float(defaults.binance_rate), step=0.01, format="%.4f")
        with rate_columns[2]:
            kontigo_in_rate = st.number_input("Kontigo — tasa de entrada", min_value=0.0, value=float(defaults.kontigo_in_rate), step=0.01, format="%.4f", help="Tasa cuando el dinero llega/se deposita en Kontigo.")
        with rate_columns[3]:
            kontigo_out_rate = st.number_input("Kontigo — tasa de salida", min_value=0.0, value=float(defaults.kontigo_out_rate), step=0.01, format="%.4f", help="Tasa cuando se retira/convierte desde Kontigo.")
        kontigo_fee_columns = st.columns(2)
        with kontigo_fee_columns[0]:
            kontigo_in_fee = st.number_input("Kontigo — comisión de entrada (%)", min_value=0.0, max_value=100.0, value=float(defaults.kontigo_in_fee), step=0.1, format="%.2f", help="Lo que Kontigo cobra por recibir el dinero, aparte de la tasa de cambio.")
        with kontigo_fee_columns[1]:
            kontigo_out_fee = st.number_input("Kontigo — comisión de salida (%)", min_value=0.0, max_value=100.0, value=float(defaults.kontigo_out_fee), step=0.1, format="%.2f", help="Lo que Kontigo cobra por retirar/convertir el dinero, aparte de la tasa de cambio.")

        st.markdown("#### Impuestos y comisiones (%)")
        fee_columns = st.columns(4)
        with fee_columns[0]:
            iva_rate = st.number_input("IVA", min_value=0.0, max_value=100.0, value=float(defaults.iva_rate), step=0.5, format="%.2f")
        with fee_columns[1]:
            igtf_rate = st.number_input("IGTF", min_value=0.0, max_value=100.0, value=float(defaults.igtf_rate), step=0.5, format="%.2f", help="Impuesto a las Grandes Transacciones Financieras, aplica a pagos en divisas/cripto.")
        with fee_columns[2]:
            mobile_payment_fee = st.number_input("Comisión pago móvil", min_value=0.0, max_value=100.0, value=float(defaults.mobile_payment_fee), step=0.1, format="%.2f")
        with fee_columns[3]:
            pos_fee = st.number_input("Comisión punto de venta / tarjeta", min_value=0.0, max_value=100.0, value=float(defaults.pos_fee), step=0.1, format="%.2f")

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
                bcv_rate=float(bcv_rate), binance_rate=float(binance_rate),
                kontigo_in_rate=float(kontigo_in_rate), kontigo_out_rate=float(kontigo_out_rate),
                kontigo_in_fee=float(kontigo_in_fee), kontigo_out_fee=float(kontigo_out_fee),
                iva_rate=float(iva_rate), igtf_rate=float(igtf_rate),
                mobile_payment_fee=float(mobile_payment_fee), pos_fee=float(pos_fee),
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

    st.markdown("#### Tasas y comisiones vigentes")
    rate_summary_columns = st.columns(4)
    rate_summary_columns[0].metric("BCV", f"{getattr(settings, 'bcv_rate', 0.0):,.4f} Bs")
    rate_summary_columns[1].metric("Binance / paralelo", f"{getattr(settings, 'binance_rate', 0.0):,.4f} Bs")
    rate_summary_columns[2].metric("Kontigo entrada", f"{getattr(settings, 'kontigo_in_rate', 0.0):,.4f} Bs")
    rate_summary_columns[3].metric("Kontigo salida", f"{getattr(settings, 'kontigo_out_rate', 0.0):,.4f} Bs")
    kontigo_fee_summary_columns = st.columns(2)
    kontigo_fee_summary_columns[0].metric("Comisión Kontigo entrada", f"{getattr(settings, 'kontigo_in_fee', 0.0):.2f}%")
    kontigo_fee_summary_columns[1].metric("Comisión Kontigo salida", f"{getattr(settings, 'kontigo_out_fee', 0.0):.2f}%")
    fee_summary_columns = st.columns(4)
    fee_summary_columns[0].metric("IVA", f"{getattr(settings, 'iva_rate', 16.0):.2f}%")
    fee_summary_columns[1].metric("IGTF", f"{getattr(settings, 'igtf_rate', 3.0):.2f}%")
    fee_summary_columns[2].metric("Comisión pago móvil", f"{getattr(settings, 'mobile_payment_fee', 0.0):.2f}%")
    fee_summary_columns[3].metric("Comisión punto de venta", f"{getattr(settings, 'pos_fee', 0.0):.2f}%")

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
