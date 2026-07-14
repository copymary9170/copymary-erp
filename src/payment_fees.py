"""Helper central para aplicar comisiones de medio de pago, IGTF y tasas de
cambio configuradas en Configuración General, sin que cada módulo tenga que
saber cuál de las dos clases `GeneralSettings` está guardada en sesión ni
reimplementar la misma lógica.

Cualquier módulo que cobre dinero puede usar esto con una sola llamada:

    from src.payment_fees import fee_breakdown, should_apply_igtf

    breakdown = fee_breakdown(total, payment_method, apply_igtf=should_apply_igtf(payment_method))
    # breakdown["net_amount"] es lo que realmente queda después de la
    # comisión del medio de pago y, si aplica, el IGTF.

Sigue funcionando aunque Configuración General no se haya llenado todavía
(devuelve 0% de comisión / IGTF, nunca falla).
"""

from __future__ import annotations

import streamlit as st

# Medios de pago sobre los que aplica el IGTF venezolano en la práctica:
# pagos en divisas o cripto. Los pagos en bolívares (efectivo, pago móvil,
# transferencia nacional, punto de venta en Bs) no lo pagan.
_IGTF_PAYMENT_METHODS = ("zelle", "binance", "kontigo", "tarjeta internacional", "cripto", "usdt")


def current_settings():
    """La configuración general guardada en sesión, sea cual sea la clase
    GeneralSettings que la haya creado (existen dos, ver general_settings.py
    y general_settings_process.py). Devuelve None si aún no se ha guardado
    nada."""
    return st.session_state.get("general_settings")


def fee_rate_for(payment_method: str) -> float:
    """Comisión (%) del medio de pago indicado, según Configuración General.
    0.0 si no hay configuración guardada o el medio no tiene comisión."""
    settings = current_settings()
    if settings is None or not hasattr(settings, "fee_for_payment_method"):
        return 0.0
    return settings.fee_for_payment_method(payment_method)


def igtf_rate() -> float:
    settings = current_settings()
    return float(getattr(settings, "igtf_rate", 0.0)) if settings is not None else 0.0


def iva_rate() -> float:
    settings = current_settings()
    return float(getattr(settings, "iva_rate", 0.0)) if settings is not None else 0.0


def exchange_rate(rate_name: str) -> float:
    """Tasa de cambio configurada por nombre: 'BCV', 'Binance', 'Kontigo
    (entrada)' o 'Kontigo (salida)'. 0.0 si no hay configuración guardada."""
    settings = current_settings()
    if settings is None or not hasattr(settings, "rate_for"):
        return 0.0
    return settings.rate_for(rate_name)


def should_apply_igtf(payment_method: str) -> bool:
    """Sugerencia de referencia, NO una regla automática: en la práctica hay
    pagos en divisas/cripto que igual quedan exentos de IGTF según cómo se
    procesen, así que decidir si aplica queda siempre en manos de quien
    registra la venta — esta función solo puede usarse para pre-marcar una
    casilla como sugerencia, nunca para aplicar el IGTF sin que alguien lo
    confirme."""
    normalized = payment_method.strip().casefold()
    return any(keyword in normalized for keyword in _IGTF_PAYMENT_METHODS)


def fee_breakdown(gross_amount: float, payment_method: str, *, apply_igtf: bool = False) -> dict:
    """Desglose completo de cuánto queda realmente de `gross_amount` después
    de la comisión del medio de pago y, si `apply_igtf` es True, el IGTF.

    El IGTF SIEMPRE queda en False por defecto: no se infiere automáticamente
    del medio de pago, porque hay pagos en divisas/cripto que igual quedan
    exentos según el caso. Quien registra la venta decide explícitamente si
    aplica, marcándolo a mano.
    """
    fee_rate = fee_rate_for(payment_method)
    fee_amount = gross_amount * fee_rate / 100
    after_fee = gross_amount - fee_amount
    applied_igtf_rate = igtf_rate() if apply_igtf else 0.0
    igtf_amount = after_fee * applied_igtf_rate / 100
    net = after_fee - igtf_amount
    return {
        "gross_amount": gross_amount,
        "payment_method": payment_method,
        "fee_rate": fee_rate,
        "fee_amount": fee_amount,
        "igtf_applied": apply_igtf,
        "igtf_rate": applied_igtf_rate,
        "igtf_amount": igtf_amount,
        "net_amount": net,
    }


def net_amount(gross_amount: float, payment_method: str, *, apply_igtf: bool = False) -> float:
    return fee_breakdown(gross_amount, payment_method, apply_igtf=apply_igtf)["net_amount"]
