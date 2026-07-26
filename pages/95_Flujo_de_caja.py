"""Flujo de caja y antigüedad de saldos (aging) — CopyMary ERP.

Página autocontenida (Streamlit multipágina): se activa solo con colocarla en
`pages/`; no requiere cablear app.py ni la navegación.

Muestra la antigüedad de las cuentas por cobrar y por pagar (al día, 1-30,
31-60, 61-90, +90 días), la posición de efectivo por método de pago y los
ingresos/egresos del mes, con equivalente referencial en USD a la tasa BCV.

Solo lectura. Lee los datos de forma defensiva (tolera nombres de campo
distintos y datos faltantes).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

try:
    from src.session_utils import read_list as _read_list
except Exception:  # pragma: no cover
    def _read_list(key: str) -> list[dict]:
        value = st.session_state.get(key, [])
        return value if isinstance(value, list) else []


BUCKETS = ("Al día / por vencer", "1-30", "31-60", "61-90", "+90")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(row: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _settings() -> dict:
    raw = st.session_state.get("general_settings")
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    try:
        return {k: getattr(raw, k) for k in dir(raw) if not k.startswith("_")}
    except Exception:
        return {}


def _bucket_for(due: date | None, today: date) -> str:
    if due is None or due >= today:
        return BUCKETS[0]
    days = (today - due).days
    if days <= 30:
        return BUCKETS[1]
    if days <= 60:
        return BUCKETS[2]
    if days <= 90:
        return BUCKETS[3]
    return BUCKETS[4]


_PAID = {"pagado", "pagada", "cobrado", "cobrada", "anulado", "anulada"}


def _aging(registry_key: str, today: date) -> tuple[dict[str, float], float]:
    buckets = {name: 0.0 for name in BUCKETS}
    total = 0.0
    for row in _read_list(registry_key):
        status = str(_first(row, "status", "estado", default="")).strip().lower()
        if status in _PAID:
            continue
        balance = _num(_first(row, "balance", "saldo", "pending", "amount", "total", default=0.0))
        if balance <= 0:
            continue
        due = _parse_date(_first(row, "due_date", "fecha_vencimiento", "vencimiento",
                                 "created_at_utc", "date", "fecha"))
        buckets[_bucket_for(due, today)] += balance
        total += balance
    return buckets, total


def _cash_flow_month(today: date) -> tuple[float, float, dict[str, float]]:
    ingresos = egresos = 0.0
    by_method: dict[str, float] = {}
    for row in _read_list("cash_movements"):
        d = _parse_date(_first(row, "created_at_utc", "date", "fecha"))
        if not d or d.year != today.year or d.month != today.month:
            continue
        amount = _num(_first(row, "amount", "monto", "total", default=0.0))
        mtype = str(_first(row, "movement_type", "type", "tipo", default="")).strip().lower()
        method = str(_first(row, "payment_method", "metodo", "method", default="Otro")) or "Otro"
        if mtype in {"ingreso", "entrada", "abono", "cobro"}:
            ingresos += amount
            by_method[method] = by_method.get(method, 0.0) + amount
        elif mtype in {"egreso", "salida", "gasto", "pago"}:
            egresos += amount
            by_method[method] = by_method.get(method, 0.0) - amount
    return ingresos, egresos, by_method


def _usd(amount: float, bcv: float) -> str:
    if bcv > 0:
        return f" (≈ {amount / bcv:,.2f} USD)"
    return ""


def render() -> None:
    today = date.today()
    settings = _settings()
    bcv = _num(_first(settings, "bcv_rate", default=0.0))

    st.title("Flujo de caja y antigüedad de saldos")
    st.caption("Posición de efectivo, ingresos/egresos del mes y aging de cuentas por "
               "cobrar y por pagar." + (" Equivalente USD referencial a tasa BCV." if bcv else ""))

    ingresos, egresos, by_method = _cash_flow_month(today)
    neto = ingresos - egresos
    row = st.columns(3)
    row[0].metric("Ingresos del mes", f"{ingresos:,.2f}")
    row[1].metric("Egresos del mes", f"{egresos:,.2f}")
    row[2].metric("Flujo neto del mes", f"{neto:,.2f}")
    if bcv:
        st.caption(f"Flujo neto {_usd(neto, bcv).strip()}")

    if by_method:
        st.subheader("Posición por método de pago (mes)")
        st.dataframe(
            [{"Método": method, "Neto": round(value, 2)} for method, value in
             sorted(by_method.items(), key=lambda kv: kv[1], reverse=True)],
            use_container_width=True, hide_index=True,
        )

    receivable_buckets, receivable_total = _aging("receivables_registry", today)
    payable_buckets, payable_total = _aging("payables_registry", today)

    st.subheader("Antigüedad de cuentas por cobrar")
    st.metric("Total por cobrar", f"{receivable_total:,.2f}" + _usd(receivable_total, bcv))
    st.dataframe(
        [{"Antigüedad": name, "Monto": round(receivable_buckets[name], 2)} for name in BUCKETS],
        use_container_width=True, hide_index=True,
    )
    overdue_recv = receivable_total - receivable_buckets[BUCKETS[0]]
    if overdue_recv > 0:
        st.warning(f"🔴 Vencido por cobrar: {overdue_recv:,.2f}" + _usd(overdue_recv, bcv))

    st.subheader("Antigüedad de cuentas por pagar")
    st.metric("Total por pagar", f"{payable_total:,.2f}" + _usd(payable_total, bcv))
    st.dataframe(
        [{"Antigüedad": name, "Monto": round(payable_buckets[name], 2)} for name in BUCKETS],
        use_container_width=True, hide_index=True,
    )
    overdue_pay = payable_total - payable_buckets[BUCKETS[0]]
    if overdue_pay > 0:
        st.warning(f"🟠 Vencido por pagar: {overdue_pay:,.2f}" + _usd(overdue_pay, bcv))

    st.caption("Solo lectura. El aging usa la fecha de vencimiento; si falta, usa la fecha del "
               "registro. El equivalente USD es referencial.")


render()
