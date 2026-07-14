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

from datetime import datetime, timezone

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


def rates_badge_html() -> str | None:
    """HTML de una franja compacta con las tasas/comisiones vigentes, para
    mostrar siempre visible (no solo cuando están desactualizadas). Devuelve
    None si todavía no se ha guardado ninguna configuración, para no mostrar
    una franja llena de ceros sin sentido."""
    settings = current_settings()
    if settings is None:
        return None
    chips = [
        ("BCV", f"Bs {getattr(settings, 'bcv_rate', 0.0):,.2f}"),
        ("Binance", f"Bs {getattr(settings, 'binance_rate', 0.0):,.2f}"),
        ("Kontigo entrada", f"Bs {getattr(settings, 'kontigo_in_rate', 0.0):,.2f} · {getattr(settings, 'kontigo_in_fee', 0.0):.1f}%"),
        ("Kontigo salida", f"Bs {getattr(settings, 'kontigo_out_rate', 0.0):,.2f} · {getattr(settings, 'kontigo_out_fee', 0.0):.1f}%"),
        ("IVA", f"{getattr(settings, 'iva_rate', 0.0):.1f}%"),
        ("IGTF", f"{getattr(settings, 'igtf_rate', 0.0):.1f}%"),
        ("Pago móvil", f"{getattr(settings, 'mobile_payment_fee', 0.0):.1f}%"),
        ("Punto de venta", f"{getattr(settings, 'pos_fee', 0.0):.1f}%"),
    ]
    stale = rates_are_stale()
    dot_color = "#e04f4f" if stale else "#22a6a1"
    items_html = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:.35rem;background:rgba(109,74,255,.06);'
        f'border:1px solid rgba(109,74,255,.14);border-radius:999px;padding:.25rem .65rem;'
        f'font-size:.78rem;font-weight:600;white-space:nowrap;">'
        f'<span style="color:#6b7280;font-weight:500;">{label}</span> {value}</span>'
        for label, value in chips
    )
    return (
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:.4rem;'
        'margin:.35rem 0 .75rem 0;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{dot_color};'
        'flex:none;"></span>'
        f'{items_html}'
        "</div>"
    )


def net_amount(gross_amount: float, payment_method: str, *, apply_igtf: bool = False) -> float:
    return fee_breakdown(gross_amount, payment_method, apply_igtf=apply_igtf)["net_amount"]


def rates_last_updated() -> str:
    """Fecha (ISO, puede venir vacía) de la última vez que se guardó
    Configuración General — se usa como proxy de 'la última vez que alguien
    revisó/confirmó las tasas', ya que guardar el formulario implica volver
    a escribir (o reconfirmar) cada tasa."""
    settings = current_settings()
    return str(getattr(settings, "rates_updated_at", "") or "") if settings is not None else ""


def rates_are_stale() -> bool:
    """True si nunca se han guardado tasas, o si no se han vuelto a guardar
    hoy (fecha UTC). No distingue fines de semana ni feriados: cualquier
    día sin guardar cuenta como desactualizado."""
    updated_at = rates_last_updated()
    if not updated_at:
        return True
    today = datetime.now(timezone.utc).date().isoformat()
    return updated_at[:10] != today


def days_since_rates_updated() -> int | None:
    """Días completos desde la última vez que se guardaron las tasas, o
    None si nunca se han guardado."""
    updated_at = rates_last_updated()
    if not updated_at:
        return None
    try:
        last = datetime.fromisoformat(updated_at)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - last).days
