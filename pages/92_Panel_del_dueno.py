"""Panel del dueño — vista ejecutiva de CopyMary ERP.

Página autocontenida (Streamlit multipágina). Se activa con solo colocar el
archivo en `pages/`; no requiere cablear app.py ni la navegación.

Resume el negocio para el dueño/gerente/financista: ingresos del mes, pedidos
activos, cuentas por cobrar y por pagar (con vencidas), valor del inventario,
gastos del mes, margen aproximado, alertas accionables y top de clientes.

Lee los datos de forma defensiva (tolera nombres de campo distintos y datos
faltantes) para no romperse ante cambios de esquema.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

try:  # helper estable del proyecto; con respaldo si cambiara
    from src.session_utils import read_list as _read_list
except Exception:  # pragma: no cover - respaldo defensivo
    def _read_list(key: str) -> list[dict]:
        value = st.session_state.get(key, [])
        return value if isinstance(value, list) else []


# ---------------------------------------------------------------------------
# Utilidades defensivas
# ---------------------------------------------------------------------------

def _num(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(row: dict, *keys: str, default: Any = None) -> Any:
    """Devuelve el primer campo presente y no vacío entre varios nombres."""
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def _amount(row: dict) -> float:
    return _num(_first(row, "total", "amount", "monto", "importe", "value", default=0.0))


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


def _row_date(row: dict) -> date | None:
    return _parse_date(_first(row, "created_at_utc", "created_at", "date", "fecha",
                              "issue_date", "sale_date"))


def _is_this_month(row: dict, today: date) -> bool:
    d = _row_date(row)
    return bool(d and d.year == today.year and d.month == today.month)


def _settings() -> dict:
    raw = st.session_state.get("general_settings")
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    # dataclass u objeto con atributos
    try:
        return {k: getattr(raw, k) for k in dir(raw) if not k.startswith("_")}
    except Exception:
        return {}


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Buenos días"
    if hour < 19:
        return "Buenas tardes"
    return "Buenas noches"


# ---------------------------------------------------------------------------
# Cálculos de negocio
# ---------------------------------------------------------------------------

_DELIVERED = {"entregado", "entregada", "completado", "completada", "cerrado", "cerrada"}
_CANCELLED = {"cancelado", "cancelada", "anulado", "anulada"}


def _sales_metrics(today: date) -> tuple[float, int]:
    sales = _read_list("sales_registry")
    revenue_month = 0.0
    active = 0
    for row in sales:
        status = str(_first(row, "order_status", "status", "estado", default="")).strip().lower()
        if status in _CANCELLED:
            continue
        if _is_this_month(row, today):
            revenue_month += _amount(row)
        if status not in _DELIVERED:
            active += 1
    return revenue_month, active


def _receivables() -> tuple[float, float, int]:
    total = overdue_amount = 0.0
    overdue_count = 0
    today = date.today()
    for row in _read_list("receivables_registry"):
        status = str(_first(row, "status", "estado", default="")).strip().lower()
        if status in {"pagado", "pagada", "cobrado", "cobrada"}:
            continue
        balance = _num(_first(row, "balance", "saldo", "pending", "amount", "total", default=0.0))
        total += balance
        due = _parse_date(_first(row, "due_date", "fecha_vencimiento", "vencimiento"))
        if due and due < today and balance > 0:
            overdue_amount += balance
            overdue_count += 1
    return total, overdue_amount, overdue_count


def _payables() -> float:
    total = 0.0
    for row in _read_list("payables_registry"):
        status = str(_first(row, "status", "estado", default="")).strip().lower()
        if status in {"pagado", "pagada"}:
            continue
        total += _num(_first(row, "balance", "saldo", "pending", "amount", "total", default=0.0))
    return total


def _inventory_snapshot() -> tuple[float, list[dict]]:
    value = 0.0
    low: list[dict] = []
    for row in _read_list("inventory_registry"):
        qty = _num(_first(row, "available_quantity", "quantity", "stock", default=0.0))
        cost = _num(_first(row, "unit_cost", "cost", default=0.0))
        value += qty * cost
        minimum = _num(_first(row, "minimum_stock", "reorder_point", default=0.0))
        if minimum > 0 and qty <= minimum:
            low.append({
                "Artículo": _first(row, "name", "product_name", default="Material"),
                "Existencia": round(qty, 2),
                "Mínimo": round(minimum, 2),
                "Unidad": _first(row, "unit_name", "unit", default=""),
            })
    return value, low


def _expenses_month(today: date) -> float:
    return sum(_amount(row) for row in _read_list("expense_records") if _is_this_month(row, today))


def _pending_receipts() -> int:
    count = 0
    for row in _read_list("purchases_registry"):
        status = str(_first(row, "receipt_status", "estado_recepcion", default="Pendiente")).strip().lower()
        if status not in {"recibida", "recibido", "cancelada", "cancelado", "cerrada"}:
            count += 1
    return count


def _top_customers(limit: int = 5) -> list[dict]:
    names = {}
    for row in _read_list("customers_registry"):
        cid = str(_first(row, "client_id", "customer_id", "id", default=""))
        names[cid] = _first(row, "name", "nombre", default=cid or "Cliente")
    totals: dict[str, float] = {}
    for row in _read_list("sales_registry"):
        status = str(_first(row, "order_status", "status", default="")).strip().lower()
        if status in _CANCELLED:
            continue
        cid = str(_first(row, "client_id", "customer_id", "cliente", default=""))
        label = names.get(cid, _first(row, "customer_name", "cliente", default="Cliente")) or "Cliente"
        totals[label] = totals.get(label, 0.0) + _amount(row)
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"Cliente": name, "Ventas": round(amount, 2)} for name, amount in ranked if amount > 0]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render() -> None:
    today = date.today()
    settings = _settings()
    business = _first(settings, "business_name", default="tu negocio")

    st.title("Panel del dueño")
    st.caption(f"{_greeting()} — vista ejecutiva de {business}. Datos de la sesión actual.")

    revenue_month, active_orders = _sales_metrics(today)
    receivable_total, receivable_overdue, overdue_count = _receivables()
    payable_total = _payables()
    inventory_value, low_stock = _inventory_snapshot()
    expenses_month = _expenses_month(today)
    pending_receipts = _pending_receipts()
    approx_result = revenue_month - expenses_month

    row1 = st.columns(4)
    row1[0].metric("Ingresos del mes", f"{revenue_month:,.2f}")
    row1[1].metric("Gastos del mes", f"{expenses_month:,.2f}")
    row1[2].metric("Resultado aprox. del mes", f"{approx_result:,.2f}")
    row1[3].metric("Pedidos activos", str(active_orders))

    row2 = st.columns(4)
    row2[0].metric("Por cobrar", f"{receivable_total:,.2f}",
                   delta=f"-{receivable_overdue:,.2f} vencido" if receivable_overdue else None,
                   delta_color="inverse")
    row2[1].metric("Por pagar", f"{payable_total:,.2f}")
    row2[2].metric("Valor de inventario", f"{inventory_value:,.2f}")
    row2[3].metric("Compras por recibir", str(pending_receipts))

    # Tasas del día
    bcv = _num(_first(settings, "bcv_rate", default=0.0))
    rates_updated = str(_first(settings, "rates_updated_at", default=""))
    updated_today = _parse_date(rates_updated) == today if rates_updated else False
    if not updated_today:
        st.warning("⚠️ Las tasas de cambio no se han confirmado hoy. Revísalas en "
                   "Administración y seguridad → Configuración General.")
    elif bcv:
        st.info(f"Tasa BCV de hoy: {bcv:,.2f}")

    # Alertas accionables
    st.subheader("Alertas")
    alerts: list[str] = []
    if overdue_count:
        alerts.append(f"🔴 {overdue_count} cuenta(s) por cobrar vencida(s) por {receivable_overdue:,.2f}.")
    if pending_receipts:
        alerts.append(f"🟠 {pending_receipts} compra(s) pendiente(s) de recepción.")
    if low_stock:
        alerts.append(f"🟡 {len(low_stock)} artículo(s) con stock bajo.")
    if alerts:
        for alert in alerts:
            st.write(alert)
    else:
        st.success("Sin alertas críticas por ahora.")

    columns = st.columns(2)
    with columns[0]:
        st.subheader("Stock bajo")
        if low_stock:
            st.dataframe(low_stock, use_container_width=True, hide_index=True)
        else:
            st.caption("Sin artículos por debajo del mínimo.")
    with columns[1]:
        st.subheader("Top de clientes")
        top = _top_customers()
        if top:
            st.dataframe(top, use_container_width=True, hide_index=True)
        else:
            st.caption("Aún no hay ventas registradas para clasificar clientes.")

    st.caption("Este panel es de solo lectura; no modifica datos.")


render()
