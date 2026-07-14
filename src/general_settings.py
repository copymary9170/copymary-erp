"""Configuración general y calculadora orientativa de costos."""

from dataclasses import dataclass

import streamlit as st

from src.assets import Asset, _get_assets
from src.components import render_info_card, render_page_header


@dataclass(frozen=True)
class GeneralSettings:
    business_name: str
    currency: str
    profit_margin: float
    pricing_method: str
    monthly_internet: float
    monthly_electricity: float
    estimated_monthly_units: int
    selected_asset_ids: tuple[str, ...]
    # Tasas de cambio de referencia (unidades de VES por 1 USD). Se guardan
    # varias porque en Venezuela conviven distintas tasas según de dónde
    # venga o hacia dónde vaya el dinero: BCV (oficial), Binance/paralelo
    # (referencia de mercado), y Kontigo, que además tiene tasa distinta de
    # entrada (cuando el dinero llega) y de salida (cuando se retira), por
    # el spread propio de la plataforma.
    bcv_rate: float = 0.0
    bcv_eur_rate: float = 0.0
    binance_rate: float = 0.0
    kontigo_in_rate: float = 0.0
    kontigo_out_rate: float = 0.0
    # Comisión (%) que cobra la propia plataforma Kontigo en cada operación,
    # distinta de la tasa de cambio.
    kontigo_in_fee: float = 0.0
    kontigo_out_fee: float = 0.0
    # Impuestos y comisiones (%) que reducen lo que realmente se recibe de
    # una venta, o encarecen lo que realmente cuesta pagar con cada medio.
    iva_rate: float = 16.0
    igtf_rate: float = 3.0
    mobile_payment_fee: float = 0.0
    pos_fee: float = 0.0
    rates_updated_at: str = ""

    @property
    def monthly_fixed_costs(self) -> float:
        return self.monthly_internet + self.monthly_electricity

    @property
    def fixed_cost_per_unit(self) -> float:
        return self.monthly_fixed_costs / self.estimated_monthly_units

    @property
    def sale_multiplier(self) -> float:
        rate = self.profit_margin / 100
        if self.pricing_method == "Margen sobre venta":
            return 1 / (1 - rate) if rate < 1 else 0.0
        return 1 + rate

    def rate_for(self, rate_name: str) -> float:
        """Tasa VES-por-USD según su nombre: 'BCV', 'Binance', 'Kontigo (entrada)'
        o 'Kontigo (salida)'. Devuelve 0.0 si el nombre no se reconoce."""
        return {
            "BCV": self.bcv_rate,
            "BCV (EUR)": self.bcv_eur_rate,
            "Binance": self.binance_rate,
            "Kontigo (entrada)": self.kontigo_in_rate,
            "Kontigo (salida)": self.kontigo_out_rate,
        }.get(rate_name, 0.0)

    def fee_for_payment_method(self, payment_method: str) -> float:
        """Comisión (%) asociada al medio de pago: pago móvil, punto de
        venta/tarjeta, o 0 para medios sin comisión configurada (efectivo,
        transferencia, etc.)."""
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
        """Monto que realmente queda de `gross_amount` después de descontar
        la comisión del medio de pago y, si aplica (pagos en divisas/cripto),
        el IGTF."""
        fee_rate = self.fee_for_payment_method(payment_method)
        net = gross_amount * (1 - fee_rate / 100)
        if apply_igtf:
            net *= (1 - self.igtf_rate / 100)
        return net


@dataclass(frozen=True)
class PriceEstimate:
    paper_cost: float
    ink_cost: float
    labor_cost: float
    indirect_cost: float
    equipment_cost: float
    other_cost: float
    quantity: int
    unit_cost: float
    total_cost: float
    unit_price: float
    total_price: float
    estimated_profit: float
    real_margin_percent: float


def _format_money(value: float, currency: str, decimals: int = 2) -> str:
    symbols = {"USD": "$", "VES": "Bs", "EUR": "€"}
    return f"{symbols.get(currency, currency)} {value:,.{decimals}f}"


def _selected_assets(settings: GeneralSettings, assets: list[Asset]) -> list[Asset]:
    selected_ids = set(settings.selected_asset_ids)
    return [asset for asset in assets if asset.asset_id in selected_ids]


def _equipment_cost_per_unit(settings: GeneralSettings, assets: list[Asset]) -> float:
    return sum(asset.depreciation_per_unit for asset in _selected_assets(settings, assets))


def _calculate_price_estimate(
    paper_cost: float,
    ink_cost: float,
    labor_cost: float,
    indirect_cost: float,
    equipment_cost: float,
    other_cost: float,
    quantity: int,
    settings: GeneralSettings,
) -> PriceEstimate:
    unit_cost = paper_cost + ink_cost + labor_cost + indirect_cost + equipment_cost + other_cost
    total_cost = unit_cost * quantity
    unit_price = unit_cost * settings.sale_multiplier
    total_price = unit_price * quantity
    estimated_profit = total_price - total_cost
    real_margin_percent = (estimated_profit / total_price * 100) if total_price else 0.0
    return PriceEstimate(
        paper_cost=paper_cost,
        ink_cost=ink_cost,
        labor_cost=labor_cost,
        indirect_cost=indirect_cost,
        equipment_cost=equipment_cost,
        other_cost=other_cost,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        unit_price=unit_price,
        total_price=total_price,
        estimated_profit=estimated_profit,
        real_margin_percent=real_margin_percent,
    )


def _go_to_assets() -> None:
    st.session_state["pending_navigation_area"] = "Activos y mantenimiento"
    st.session_state["pending_navigation_page"] = "Activos"
    st.rerun()


def render_general_settings() -> None:
    """Renderiza la configuración y obtiene los equipos desde Activos."""
    with st.container(border=True):
        render_page_header(
            "Configuración General",
            "Define parámetros básicos y calcula precios orientativos para el negocio.",
        )
        st.caption("Los valores se conservan únicamente mientras esta sesión permanezca abierta.")

    st.warning(
        "Esta función todavía no utiliza base de datos. Al cerrar o reiniciar la aplicación, "
        "la configuración y los cálculos pueden perderse."
    )

    assets = _get_assets()
    asset_options = {asset.asset_id: asset for asset in assets}
    default_settings = GeneralSettings(
        business_name="Copy Mary",
        currency="USD",
        profit_margin=40.0,
        pricing_method="Margen sobre venta",
        monthly_internet=5.0,
        monthly_electricity=3.0,
        estimated_monthly_units=200,
        selected_asset_ids=tuple(asset_options),
    )
    stored_settings = st.session_state.get("general_settings")
    defaults = stored_settings if isinstance(stored_settings, GeneralSettings) else default_settings
    valid_default_ids = [asset_id for asset_id in defaults.selected_asset_ids if asset_id in asset_options]

    st.subheader("Datos del negocio")
    with st.form("general_settings_form"):
        business_name = st.text_input("Nombre del negocio", value=defaults.business_name, max_chars=80)
        currency = st.selectbox(
            "Moneda principal",
            options=("USD", "VES", "EUR"),
            index=("USD", "VES", "EUR").index(defaults.currency),
        )

        price_columns = st.columns(2)
        with price_columns[0]:
            pricing_method = st.selectbox(
                "Método de fijación de precio",
                options=("Margen sobre venta", "Recargo sobre costo"),
                index=("Margen sobre venta", "Recargo sobre costo").index(defaults.pricing_method),
                help=(
                    "Margen sobre venta calcula precio = costo / (1 - margen). "
                    "Recargo sobre costo calcula precio = costo × (1 + porcentaje)."
                ),
            )
        with price_columns[1]:
            max_percentage = 99.0 if pricing_method == "Margen sobre venta" else 500.0
            profit_margin = st.number_input(
                "Margen objetivo (%)" if pricing_method == "Margen sobre venta" else "Recargo sobre costo (%)",
                min_value=0.0,
                max_value=max_percentage,
                value=min(float(defaults.profit_margin), max_percentage),
                step=1.0,
            )

        cost_columns = st.columns(3)
        with cost_columns[0]:
            monthly_internet = st.number_input(
                "Internet mensual imputado al negocio",
                min_value=0.0,
                value=float(defaults.monthly_internet),
                step=1.0,
            )
        with cost_columns[1]:
            monthly_electricity = st.number_input(
                "Electricidad mensual imputada al negocio",
                min_value=0.0,
                value=float(defaults.monthly_electricity),
                step=1.0,
            )
        with cost_columns[2]:
            estimated_monthly_units = st.number_input(
                "Unidades productivas equivalentes al mes",
                min_value=1,
                value=int(defaults.estimated_monthly_units),
                step=1,
                help=(
                    "Base utilizada para repartir costos fijos. Por ahora representa una unidad productiva "
                    "estándar; más adelante podrá sustituirse por horas máquina o centros de costo."
                ),
            )

        st.markdown("#### Equipos productivos tomados desde Activos")
        if assets:
            selected_asset_ids = st.multiselect(
                "Selecciona los activos que participan en este cálculo",
                options=list(asset_options),
                default=valid_default_ids,
                format_func=lambda asset_id: (
                    f"{asset_options[asset_id].name} · {asset_options[asset_id].category} · "
                    f"{_format_money(asset_options[asset_id].acquisition_cost, currency)} · "
                    f"{asset_options[asset_id].lifetime_units:,} unidades"
                ),
                help=(
                    "El nombre, costo de adquisición y vida útil se leen automáticamente de Activos. "
                    "Cualquier corrección debe hacerse en ese módulo."
                ),
            )
            preview_cost = sum(asset_options[item].depreciation_per_unit for item in selected_asset_ids)
            st.caption(
                f"{len(selected_asset_ids)} activo(s) seleccionado(s) · Depreciación combinada: "
                f"{_format_money(preview_cost, currency, 4)} por unidad."
            )
        else:
            selected_asset_ids = []
            st.info("No hay activos registrados. Registra primero la impresora o equipo en el módulo Activos.")

        st.markdown("#### Tasas de cambio de referencia (VES por 1 USD)")
        st.caption("Cada una se guarda por separado porque suelen ser distintas: BCV es la oficial, Binance/paralelo es la de mercado, y Kontigo tiene una tasa cuando el dinero entra y otra cuando sale.")
        rate_columns = st.columns(4)
        with rate_columns[0]:
            bcv_rate = st.number_input("Tasa BCV", min_value=0.0, value=float(defaults.bcv_rate), step=0.01, format="%.4f")
        with rate_columns[1]:
            binance_rate = st.number_input("Tasa Binance / paralelo", min_value=0.0, value=float(defaults.binance_rate), step=0.01, format="%.4f")
        with rate_columns[2]:
            kontigo_in_rate = st.number_input("Kontigo — tasa de entrada", min_value=0.0, value=float(defaults.kontigo_in_rate), step=0.01, format="%.4f", help="Tasa cuando el dinero llega/se deposita en Kontigo.")
        with rate_columns[3]:
            kontigo_out_rate = st.number_input("Kontigo — tasa de salida", min_value=0.0, value=float(defaults.kontigo_out_rate), step=0.01, format="%.4f", help="Tasa cuando se retira/convierte desde Kontigo.")
        bcv_eur_rate = st.number_input("Tasa BCV Euro (VES por 1 EUR)", min_value=0.0, value=float(defaults.bcv_eur_rate), step=0.01, format="%.4f", help="La tasa oficial del BCV para el euro, aparte de la del dólar.")
        kontigo_fee_columns = st.columns(2)
        with kontigo_fee_columns[0]:
            kontigo_in_fee = st.number_input("Kontigo — comisión de entrada (%)", min_value=0.0, max_value=100.0, value=float(defaults.kontigo_in_fee), step=0.1, format="%.2f")
        with kontigo_fee_columns[1]:
            kontigo_out_fee = st.number_input("Kontigo — comisión de salida (%)", min_value=0.0, max_value=100.0, value=float(defaults.kontigo_out_fee), step=0.1, format="%.2f")

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

        submitted = st.form_submit_button(
            "Guardar configuración", type="primary", use_container_width=True,
        )

    if not assets and st.button("Ir al módulo Activos", use_container_width=True):
        _go_to_assets()

    if submitted:
        cleaned_name = business_name.strip()
        if not cleaned_name:
            st.error("El nombre del negocio no puede quedar vacío.")
        else:
            st.session_state.general_settings = GeneralSettings(
                business_name=cleaned_name,
                currency=currency,
                profit_margin=float(profit_margin),
                pricing_method=pricing_method,
                monthly_internet=float(monthly_internet),
                monthly_electricity=float(monthly_electricity),
                estimated_monthly_units=int(estimated_monthly_units),
                selected_asset_ids=tuple(selected_asset_ids),
                bcv_rate=float(bcv_rate),
                bcv_eur_rate=float(bcv_eur_rate),
                binance_rate=float(binance_rate),
                kontigo_in_rate=float(kontigo_in_rate),
                kontigo_out_rate=float(kontigo_out_rate),
                kontigo_in_fee=float(kontigo_in_fee),
                kontigo_out_fee=float(kontigo_out_fee),
                iva_rate=float(iva_rate),
                igtf_rate=float(igtf_rate),
                mobile_payment_fee=float(mobile_payment_fee),
                pos_fee=float(pos_fee),
            )
            st.session_state.pop("price_estimate", None)
            st.success("Configuración guardada durante esta sesión.")
            st.rerun()

    settings = st.session_state.get("general_settings", defaults)
    selected_assets = _selected_assets(settings, assets)
    equipment_cost_per_unit = _equipment_cost_per_unit(settings, assets)

    st.divider()
    st.subheader("Resumen calculado")
    summary_columns = st.columns(4)
    summary_columns[0].metric("Negocio", settings.business_name)
    summary_columns[1].metric(
        "Costo fijo por unidad equivalente",
        _format_money(settings.fixed_cost_per_unit, settings.currency),
    )
    summary_columns[2].metric(
        "Depreciación automática por unidad",
        _format_money(equipment_cost_per_unit, settings.currency, 4),
    )
    summary_columns[3].metric(
        "Factor de precio",
        f"× {settings.sale_multiplier:.4f}",
        help=f"Método utilizado: {settings.pricing_method}.",
    )

    cards = st.columns(2)
    with cards[0]:
        render_info_card(
            "Prorrateo de costos fijos",
            f"Internet y electricidad se distribuyen entre {settings.estimated_monthly_units:,} "
            f"unidades productivas equivalentes. El resultado es "
            f"{_format_money(settings.fixed_cost_per_unit, settings.currency)} por unidad.",
            "COSTO INDIRECTO SUGERIDO",
        )
    with cards[1]:
        if selected_assets:
            detail = (
                f"Se incluyen {len(selected_assets)} activo(s). La reserva combinada es "
                f"{_format_money(equipment_cost_per_unit, settings.currency, 4)} por unidad, "
                "calculada con el costo y la vida útil registrados en Activos."
            )
        else:
            detail = "No hay activos productivos seleccionados. La depreciación aplicada es cero."
        render_info_card("Reserva para reemplazo de equipos", detail, "DEPRECIACIÓN AUTOMÁTICA")

    if selected_assets:
        st.markdown("#### Desglose de activos incluidos")
        for asset in selected_assets:
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{asset.name}**  \n{asset.category}")
                cols[1].metric("Costo", _format_money(asset.acquisition_cost, settings.currency))
                cols[2].metric("Vida útil", f"{asset.lifetime_units:,}")
                cols[3].metric(
                    "Depreciación/unidad",
                    _format_money(asset.depreciation_per_unit, settings.currency, 4),
                )
    else:
        st.warning("Selecciona al menos un activo productivo para incorporar su depreciación al costeo.")

    st.markdown("#### Tasas y comisiones vigentes")
    rate_summary_columns = st.columns(5)
    rate_summary_columns[0].metric("BCV", f"{settings.bcv_rate:,.4f} Bs")
    rate_summary_columns[1].metric("BCV Euro", f"{settings.bcv_eur_rate:,.4f} Bs")
    rate_summary_columns[2].metric("Binance / paralelo", f"{settings.binance_rate:,.4f} Bs")
    rate_summary_columns[3].metric("Kontigo entrada", f"{settings.kontigo_in_rate:,.4f} Bs")
    rate_summary_columns[4].metric("Kontigo salida", f"{settings.kontigo_out_rate:,.4f} Bs")
    kontigo_fee_summary_columns = st.columns(2)
    kontigo_fee_summary_columns[0].metric("Comisión Kontigo entrada", f"{settings.kontigo_in_fee:.2f}%")
    kontigo_fee_summary_columns[1].metric("Comisión Kontigo salida", f"{settings.kontigo_out_fee:.2f}%")
    fee_summary_columns = st.columns(4)
    fee_summary_columns[0].metric("IVA", f"{settings.iva_rate:.2f}%")
    fee_summary_columns[1].metric("IGTF", f"{settings.igtf_rate:.2f}%")
    fee_summary_columns[2].metric("Comisión pago móvil", f"{settings.mobile_payment_fee:.2f}%")
    fee_summary_columns[3].metric("Comisión punto de venta", f"{settings.pos_fee:.2f}%")
    if settings.kontigo_in_rate and settings.kontigo_out_rate and settings.kontigo_in_rate != settings.kontigo_out_rate:
        spread = abs(settings.kontigo_out_rate - settings.kontigo_in_rate) / settings.kontigo_in_rate * 100
        st.caption(f"Spread entre entrada y salida de Kontigo: {spread:.2f}%.")

    st.divider()
    st.subheader("Calculadora detallada de costos")
    st.caption(
        f"Suma los costos por unidad y aplica el método «{settings.pricing_method}» con "
        f"{settings.profit_margin:.0f}%."
    )

    with st.form("price_estimate_form"):
        first_row = st.columns(3)
        with first_row[0]:
            paper_cost = st.number_input("Papel por unidad", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        with first_row[1]:
            ink_cost = st.number_input("Tinta por unidad", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        with first_row[2]:
            labor_cost = st.number_input("Mano de obra por unidad", min_value=0.0, value=0.0, step=0.01, format="%.2f")

        second_row = st.columns(4)
        with second_row[0]:
            indirect_cost = st.number_input(
                "Gastos indirectos por unidad",
                min_value=0.0,
                value=float(settings.fixed_cost_per_unit),
                step=0.01,
                format="%.2f",
                help="Se propone desde el prorrateo mensual, pero puede ajustarse para un trabajo específico.",
            )
        with second_row[1]:
            st.number_input(
                "Depreciación automática de activos",
                min_value=0.0,
                value=float(equipment_cost_per_unit),
                step=0.0001,
                format="%.4f",
                disabled=True,
                help="Valor bloqueado: se obtiene exclusivamente de los activos seleccionados.",
            )
        with second_row[2]:
            other_cost = st.number_input("Otros costos por unidad", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        with second_row[3]:
            quantity = st.number_input("Cantidad", min_value=1, value=1, step=1)

        calculate_submitted = st.form_submit_button(
            "Calcular precio detallado", type="primary", use_container_width=True,
        )

    if calculate_submitted:
        st.session_state.price_estimate = _calculate_price_estimate(
            paper_cost=float(paper_cost),
            ink_cost=float(ink_cost),
            labor_cost=float(labor_cost),
            indirect_cost=float(indirect_cost),
            equipment_cost=float(equipment_cost_per_unit),
            other_cost=float(other_cost),
            quantity=int(quantity),
            settings=settings,
        )

    estimate = st.session_state.get("price_estimate")
    if estimate is not None:
        st.subheader("Resultado")
        result_columns = st.columns(5)
        result_columns[0].metric("Costo por unidad", _format_money(estimate.unit_cost, settings.currency))
        result_columns[1].metric("Precio por unidad", _format_money(estimate.unit_price, settings.currency))
        result_columns[2].metric("Venta total", _format_money(estimate.total_price, settings.currency))
        result_columns[3].metric("Ganancia estimada", _format_money(estimate.estimated_profit, settings.currency))
        result_columns[4].metric("Margen real", f"{estimate.real_margin_percent:.2f}%")

        render_info_card(
            "Resultado de la estimación",
            f"Para {estimate.quantity} unidad(es), el costo total es "
            f"{_format_money(estimate.total_cost, settings.currency)}, la venta orientativa es "
            f"{_format_money(estimate.total_price, settings.currency)} y la ganancia estimada es "
            f"{_format_money(estimate.estimated_profit, settings.currency)}. "
            f"El margen real sobre la venta es {estimate.real_margin_percent:.2f}%.",
            "RESULTADO TEMPORAL",
        )

    st.info(
        "Los equipos no se escriben manualmente aquí. Nombre, costo, vida útil y depreciación "
        "provienen del módulo Activos."
    )
