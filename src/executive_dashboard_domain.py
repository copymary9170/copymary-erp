"""Cálculos puros para tablero ejecutivo, operación y aprobaciones."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Iterable


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_date(value) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value or "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _active(row: dict) -> bool:
    status = str(row.get("order_status", row.get("status", ""))).strip().casefold()
    return status not in {"cancelado", "cancelada", "anulado", "anulada"}


def product_profitability(sales: Iterable[dict]) -> list[dict]:
    """Agrupa ingresos, costos, utilidad y margen por producto/servicio."""
    groups: dict[str, dict] = defaultdict(lambda: {"revenue": 0.0, "cost": 0.0, "units": 0.0})
    for sale in sales:
        if not _active(sale):
            continue
        product = str(sale.get("product_name") or sale.get("description") or "Sin identificar")
        revenue = _num(sale.get("net_amount", sale.get("total")))
        cost = _num(sale.get("actual_cost", sale.get("estimated_cost")))
        groups[product]["revenue"] += revenue
        groups[product]["cost"] += cost
        groups[product]["units"] += _num(sale.get("quantity"), 1.0)
    result = []
    for product, values in groups.items():
        profit = values["revenue"] - values["cost"]
        margin = profit / values["revenue"] * 100 if values["revenue"] else 0.0
        result.append({"product": product, **values, "profit": profit, "margin_pct": margin})
    return sorted(result, key=lambda row: row["profit"], reverse=True)


def net_margin(sales: Iterable[dict], operating_expenses: float = 0.0) -> dict:
    revenue = sum(_num(row.get("net_amount", row.get("total"))) for row in sales if _active(row))
    costs = sum(_num(row.get("actual_cost", row.get("estimated_cost"))) for row in sales if _active(row))
    net_profit = revenue - costs - _num(operating_expenses)
    return {
        "revenue": revenue,
        "costs": costs,
        "operating_expenses": _num(operating_expenses),
        "net_profit": net_profit,
        "net_margin_pct": net_profit / revenue * 100 if revenue else 0.0,
    }


def break_even(fixed_costs: float, contribution_margin_pct: float) -> dict:
    margin = _num(contribution_margin_pct) / 100
    if margin <= 0:
        raise ValueError("El margen de contribución debe ser mayor que cero.")
    sales_required = _num(fixed_costs) / margin
    return {"fixed_costs": _num(fixed_costs), "contribution_margin_pct": contribution_margin_pct, "sales_required": sales_required}


def top_customers(sales: Iterable[dict], customers: Iterable[dict], limit: int = 5) -> list[dict]:
    names = {str(row.get("client_id", "")): str(row.get("name", "Cliente")) for row in customers}
    totals: dict[str, float] = defaultdict(float)
    orders: dict[str, int] = defaultdict(int)
    for sale in sales:
        if not _active(sale):
            continue
        client_id = str(sale.get("client_id", ""))
        totals[client_id] += _num(sale.get("net_amount", sale.get("total")))
        orders[client_id] += 1
    rows = [{"client_id": key, "customer": names.get(key, "Sin cliente"), "sales": value, "orders": orders[key]} for key, value in totals.items()]
    return sorted(rows, key=lambda row: row["sales"], reverse=True)[: max(limit, 0)]


def sales_period_comparison(sales: Iterable[dict], current_start: date, current_end: date, previous_start: date, previous_end: date) -> dict:
    current = previous = 0.0
    for sale in sales:
        if not _active(sale):
            continue
        sold = _as_date(sale.get("created_at_utc") or sale.get("date"))
        amount = _num(sale.get("net_amount", sale.get("total")))
        if sold and current_start <= sold <= current_end:
            current += amount
        if sold and previous_start <= sold <= previous_end:
            previous += amount
    variation = current - previous
    return {"current": current, "previous": previous, "variation": variation, "variation_pct": variation / previous * 100 if previous else (100.0 if current else 0.0)}


def delivery_performance(orders: Iterable[dict], today: date | None = None) -> dict:
    current = today or date.today()
    on_time = late = pending = 0
    for order in orders:
        if not _active(order):
            continue
        promised = _as_date(order.get("promised_date") or order.get("delivery_date"))
        delivered = _as_date(order.get("delivered_at") or order.get("delivered_at_utc"))
        if delivered:
            if promised and delivered <= promised:
                on_time += 1
            else:
                late += 1
        elif promised and promised < current:
            late += 1
        else:
            pending += 1
    completed = on_time + late
    return {"on_time": on_time, "late": late, "pending": pending, "on_time_pct": on_time / completed * 100 if completed else 0.0}


def capacity_usage(production_orders: Iterable[dict]) -> dict:
    used = sum(_num(row.get("used_minutes", row.get("actual_minutes"))) for row in production_orders if _active(row))
    available = sum(_num(row.get("available_minutes", row.get("capacity_minutes"))) for row in production_orders if _active(row))
    return {"used_minutes": used, "available_minutes": available, "usage_pct": used / available * 100 if available else 0.0}


def average_cycle_time(production_orders: Iterable[dict]) -> float:
    values = []
    for row in production_orders:
        started = row.get("started_at") or row.get("started_at_utc")
        finished = row.get("finished_at") or row.get("finished_at_utc")
        try:
            start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
            finish_dt = datetime.fromisoformat(str(finished).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        values.append((finish_dt - start_dt).total_seconds() / 3600)
    return sum(values) / len(values) if values else 0.0


def waste_by_process(records: Iterable[dict]) -> list[dict]:
    groups: dict[str, dict] = defaultdict(lambda: {"input": 0.0, "waste": 0.0})
    for row in records:
        process = str(row.get("process") or row.get("stage") or "Sin proceso")
        groups[process]["input"] += _num(row.get("input_quantity", row.get("used_quantity")))
        groups[process]["waste"] += _num(row.get("waste_quantity", row.get("scrap_quantity")))
    result = []
    for process, values in groups.items():
        pct = values["waste"] / values["input"] * 100 if values["input"] else 0.0
        result.append({"process": process, **values, "waste_pct": pct})
    return sorted(result, key=lambda row: row["waste"], reverse=True)


def approval_trace(*collections: Iterable[dict]) -> list[dict]:
    """Normaliza aprobaciones de compras, ajustes y cambios de precio."""
    rows = []
    for collection in collections:
        for row in collection:
            actor = row.get("approved_by") or row.get("authorized_by") or row.get("changed_by")
            if not actor:
                continue
            rows.append({
                "entity_type": str(row.get("entity_type") or row.get("type") or row.get("category") or "Registro"),
                "entity_id": str(row.get("entity_id") or row.get("purchase_id") or row.get("adjustment_id") or row.get("price_change_id") or ""),
                "approved_by": str(actor),
                "approved_at": str(row.get("approved_at_utc") or row.get("authorized_at_utc") or row.get("changed_at_utc") or row.get("updated_at_utc") or ""),
                "status": str(row.get("approval_status") or row.get("status") or "Aprobado"),
                "reason": str(row.get("approval_note") or row.get("reason") or row.get("notes") or ""),
            })
    return sorted(rows, key=lambda row: row["approved_at"], reverse=True)
